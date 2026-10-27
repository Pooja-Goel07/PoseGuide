/*
 * ╔══════════════════════════════════════════════════════════════════════╗
 * ║  PoseGuide - ESP32 Mock Posture Firmware (Assessment-6 iteration)     ║
 * ║  Real Arduino/ESP32 firmware, HTTP POST transport, 3-feature model    ║
 * ╠══════════════════════════════════════════════════════════════════════╣
 * ║  WHY THIS IS A "MOCK":                                                 ║
 * ║  There is no physical MPU-6050 wired up for this iteration, so the     ║
 * ║  sensor reads are STUBBED with plausible generated posture values      ║
 * ║  (see sampleReading()) instead of calling Wire / Adafruit_MPU6050.     ║
 * ║  Everything else behaves like real firmware: Wi-Fi join, JSON build,   ║
 * ║  HTTPClient POST at a fixed rate. To use real sensors later, replace   ║
 * ║  ONLY sampleReading() with actual IMU reads - nothing else changes.    ║
 * ╠══════════════════════════════════════════════════════════════════════╣
 * ║  Feature model (flex sensor removed this iteration):                   ║
 * ║     [torso_pitch, torso_roll, neck_relative_pitch]                     ║
 * ║  neck_relative_pitch is derived SERVER-SIDE as |neck.pitch-torso.pitch|║
 * ║  so we only send raw torso.pitch/roll + neck.pitch.                    ║
 * ╠══════════════════════════════════════════════════════════════════════╣
 * ║  The Gaussian POSTURE_STATES parameters below MIRROR the backend's     ║
 * ║  ml/constants.py so live firmware data matches the synthetic dataset.  ║
 * ╚══════════════════════════════════════════════════════════════════════╝
 *
 * Required libraries (Arduino Library Manager):
 *   - WiFi        (built-in with the ESP32 board package)
 *   - HTTPClient  (built-in with the ESP32 board package)
 *   - ArduinoJson (by Benoit Blanchon, v7+)
 *
 * NOTE: This sketch is not expected to be flashed during this session; it is
 * written to be correct, clean and buildable. Live firmware testing is out of
 * scope for the current build.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <math.h>

// ════════════════════════════════════════════════════════════════════════
//  1. USER CONFIG  ─── fill these in before flashing ─────────────────────
// ════════════════════════════════════════════════════════════════════════
#define WIFI_SSID       "YOUR_WIFI_SSID"       // <-- CHANGE ME
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"   // <-- CHANGE ME

// IP address / hostname of the machine running the FastAPI backend, e.g. the
// value printed by `ipconfig` (Windows) or `hostname -I` (Linux/mac).
#define SERVER_HOST     "192.168.1.100"        // <-- CHANGE ME
#define SERVER_PORT     8000
#define SENSOR_ENDPOINT "/api/sensor-data"

// Send interval (spec: every ~300-500 ms).
#define SEND_PERIOD_MS  400

// ════════════════════════════════════════════════════════════════════════
//  2. FAULT INJECTION  ─── demonstrable, NOT constant nuisances ──────────
//  Assessment-6 needs >=2 fault conditions. Both are OFF-ish by default via
//  low duty cycles so normal demos are clean, and can be dialled up to show
//  the backend catching them on request.
// ════════════════════════════════════════════════════════════════════════
#define ENABLE_FAULT_INJECTION   1   // master switch (1 = on, 0 = off)

// Fault A: invalid / out-of-range reading. 1-in-N readings is corrupted so the
// backend's validation logic (NaN / |angle|>180) has something real to reject.
#define ENABLE_INVALID_FAULT     1
#define INVALID_EVERY_N          40  // ~1 bad reading per 40 (0 = never)

// Fault B: sensor/network dropout. Every DROPOUT_EVERY_N readings we go silent
// for a random 10-20 s so the backend's staleness/offline detection triggers.
#define ENABLE_DROPOUT_FAULT     1
#define DROPOUT_EVERY_N          120 // ~1 dropout per 120 readings (0 = never)
#define DROPOUT_MIN_MS           10000
#define DROPOUT_MAX_MS           20000

// ════════════════════════════════════════════════════════════════════════
//  3. SYNTHETIC POSTURE MODEL  ─── mirrors backend ml/constants.py ────────
// ════════════════════════════════════════════════════════════════════════
enum PostureState { NORMAL, SLOUCH, FORWARD_HEAD, LATERAL_LEAN, CRITICAL, N_STATES };

// (mean, std) for torso.pitch, torso.roll and the neck OFFSET (added to torso
// pitch). Keep these identical to POSTURE_STATES in ml/constants.py.
struct StateParams {
  float pitchMean, pitchStd;
  float rollMean,  rollStd;
  float neckMean,  neckStd;   // neck offset above torso pitch
  float weight;               // relative visit frequency
};

const StateParams STATES[N_STATES] = {
  /* NORMAL       */ {  3.0f, 3.0f,  0.0f, 3.0f,  5.0f, 3.0f, 0.55f },
  /* SLOUCH       */ { 32.0f, 4.0f,  2.0f, 4.0f,  8.0f, 3.0f, 0.15f },
  /* FORWARD_HEAD */ {  8.0f, 3.0f,  1.0f, 3.0f, 26.0f, 4.0f, 0.13f },
  /* LATERAL_LEAN */ {  5.0f, 3.0f, 20.0f, 4.0f,  6.0f, 3.0f, 0.12f },
  /* CRITICAL     */ { 46.0f, 4.0f,  3.0f, 4.0f, 10.0f, 3.0f, 0.05f },
};

// ── Runtime state ────────────────────────────────────────────────────────
unsigned long lastSendTime = 0;
unsigned long readingCount = 0;

// Hold each posture state for a few readings ("dwell") so excursions last a
// couple of seconds on the dashboard instead of flickering every packet.
PostureState  currentState  = NORMAL;
int           dwellRemaining = 0;

#define STATUS_LED 2

// ════════════════════════════════════════════════════════════════════════
//  SETUP
// ════════════════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(200);
  pinMode(STATUS_LED, OUTPUT);
  randomSeed(esp_random());

  Serial.println();
  Serial.println("=== PoseGuide Mock HTTP Firmware ===");
  Serial.println("Sensor reads are STUBBED (no physical MPU-6050).");

  connectWiFi();
  Serial.println("--- entering main loop ---");
}

// ════════════════════════════════════════════════════════════════════════
//  MAIN LOOP
// ════════════════════════════════════════════════════════════════════════
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    return;
  }

  unsigned long now = millis();
  if (now - lastSendTime < SEND_PERIOD_MS) return;
  lastSendTime = now;

  readingCount++;

  // ── Fault B: periodic dropout (go silent for 10-20 s) ──────────────────
#if ENABLE_FAULT_INJECTION && ENABLE_DROPOUT_FAULT
  if (DROPOUT_EVERY_N > 0 && readingCount % DROPOUT_EVERY_N == 0) {
    unsigned long dropMs = random(DROPOUT_MIN_MS, DROPOUT_MAX_MS + 1);
    Serial.printf("[FAULT B] Simulated dropout - going silent for %lu ms\n", dropMs);
    delay(dropMs);
    lastSendTime = millis();
    return;
  }
#endif

  // ── Generate a plausible reading ───────────────────────────────────────
  float torsoPitch, torsoRoll, neckPitch;
  sampleReading(torsoPitch, torsoRoll, neckPitch);

  // ── Fault A: occasionally corrupt the reading ──────────────────────────
  bool corrupted = false;
#if ENABLE_FAULT_INJECTION && ENABLE_INVALID_FAULT
  if (INVALID_EVERY_N > 0 && readingCount % INVALID_EVERY_N == 0) {
    corrupted = true;
    // Alternate between out-of-physical-range and NaN so both validation
    // branches on the backend get exercised.
    if ((readingCount / INVALID_EVERY_N) % 2 == 0) {
      torsoPitch = 999.0f;              // |angle| > 180 -> out_of_range
      Serial.println("[FAULT A] Injecting out-of-range torso.pitch = 999");
    } else {
      torsoPitch = NAN;                 // NaN -> non_finite
      Serial.println("[FAULT A] Injecting NaN torso.pitch");
    }
  }
#endif

  sendReading(torsoPitch, torsoRoll, neckPitch);
  (void)corrupted;
}

// ════════════════════════════════════════════════════════════════════════
//  SENSOR STUB  ─── replace ONLY this with real IMU reads for hardware ────
// ════════════════════════════════════════════════════════════════════════
void sampleReading(float &torsoPitch, float &torsoRoll, float &neckPitch) {
  // Advance the posture state machine when the current dwell expires.
  if (dwellRemaining <= 0) {
    currentState  = pickWeightedState();
    dwellRemaining = random(4, 11);   // hold this posture for 4-10 readings
  }
  dwellRemaining--;

  const StateParams &p = STATES[currentState];
  torsoPitch      = gaussian(p.pitchMean, p.pitchStd);
  torsoRoll       = gaussian(p.rollMean,  p.rollStd);
  float neckOffset = gaussian(p.neckMean, p.neckStd);

  // Lateral lean tips to either side.
  if (currentState == LATERAL_LEAN && random(0, 2) == 0) torsoRoll = -torsoRoll;

  neckPitch = torsoPitch + neckOffset;
}

// Weighted random posture-state selection (matches STATE_WEIGHTS).
PostureState pickWeightedState() {
  float total = 0.0f;
  for (int i = 0; i < N_STATES; i++) total += STATES[i].weight;
  float r = (float)random(0, 10000) / 10000.0f * total;
  float acc = 0.0f;
  for (int i = 0; i < N_STATES; i++) {
    acc += STATES[i].weight;
    if (r <= acc) return (PostureState)i;
  }
  return NORMAL;
}

// Box-Muller Gaussian sample (Arduino has no gauss()).
float gaussian(float mean, float std) {
  float u1 = (random(1, 10000)) / 10000.0f;   // (0,1], avoid log(0)
  float u2 = (random(0, 10000)) / 10000.0f;
  float z  = sqrtf(-2.0f * logf(u1)) * cosf(2.0f * PI * u2);
  return mean + std * z;
}

// ════════════════════════════════════════════════════════════════════════
//  NETWORK
// ════════════════════════════════════════════════════════════════════════
void sendReading(float torsoPitch, float torsoRoll, float neckPitch) {
  JsonDocument doc;
  JsonObject torso = doc["torso"].to<JsonObject>();
  torso["pitch"] = torsoPitch;
  torso["roll"]  = torsoRoll;
  JsonObject neck = doc["neck"].to<JsonObject>();
  neck["pitch"]  = neckPitch;
  doc["timestamp"] = (double)millis();

  String body;
  serializeJson(doc, body);

  HTTPClient http;
  char url[96];
  snprintf(url, sizeof(url), "http://%s:%d%s", SERVER_HOST, SERVER_PORT, SENSOR_ENDPOINT);
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  int code = http.POST(body);
  if (code > 0) {
    digitalWrite(STATUS_LED, HIGH); delay(2); digitalWrite(STATUS_LED, LOW);
    Serial.printf("POST %d  %s\n", code, body.c_str());
  } else {
    Serial.printf("POST failed: %s\n", http.errorToString(code).c_str());
  }
  http.end();
}

void connectWiFi() {
  Serial.printf("Connecting to Wi-Fi \"%s\"", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500); Serial.print("."); attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWi-Fi connected. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\nWi-Fi failed - retrying in loop.");
  }
}
