/*
 * ═══════════════════════════════════════════════════════════
 *  PoseGuide – Live Sensor → Backend
 *  File: Hardware/posture_live.ino
 * ═══════════════════════════════════════════════════════════
 *
 *  Reads BOTH MPU6050 sensors over I2C and POSTs real data
 *  to the FastAPI backend every 300ms. The dashboard stick
 *  figure will respond live to your actual posture.
 *
 *  Flex sensor is NOT connected — hardcoded at 30.0 (neutral).
 *
 *  WIRING:
 *    MPU #1 (Torso/T4):  AD0 → GND  → address 0x68
 *    MPU #2 (Neck/C7) :  AD0 → 3.3V → address 0x69
 *    Both share: SDA → GPIO 21, SCL → GPIO 22
 *
 *  HOW IT WORKS:
 *    1. Connects to WiFi hotspot
 *    2. Reads both MPU6050s (accelerometer only — simple tilt)
 *    3. Applies a 4-sample rolling average to smooth noise
 *    4. POSTs JSON to POST /api/sensor-data every 300ms
 *    5. Dashboard polls GET /api/latest and animates stick figure
 *
 *  REQUIRED LIBRARIES: ArduinoJson  (no others needed)
 * ═══════════════════════════════════════════════════════════
 */

#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── WiFi ────────────────────────────────────────────────────
const char* WIFI_SSID     = "Pooja";         // ← your hotspot name
const char* WIFI_PASSWORD = "poseguide";     // ← your hotspot password

// ── Backend ─────────────────────────────────────────────────
const char* BACKEND_IP   = "10.156.233.89"; // ← your PC's IP on hotspot
const int   BACKEND_PORT = 8000;

// ── I2C ─────────────────────────────────────────────────────
#define SDA_PIN  21
#define SCL_PIN  22
#define MPU_TORSO  0x68   // AD0 → GND
#define MPU_NECK   0x69   // AD0 → 3.3V

#define MPU_REG_PWR_MGMT_1   0x6B
#define MPU_REG_ACCEL_XOUT_H 0x3B

// ── Flex sensor (GPIO 34 — voltage divider with 1kΩ) ──────
#define FLEX_PIN      34
// Calibration: run flex_sensor_test.ino first, note min/max, update here
const int FLEX_FLAT   = 370;   // ADC value when sensor is FLAT (not bent)
const int FLEX_BENT   =  60;   // ADC value when sensor is FULLY BENT

// ── Mounting Orientation Offsets ────────────────────────────
// The MPU measures angle from horizontal (flat = 0°).
// If you mount the sensor VERTICALLY on your back:
//   - spine faces forward  → set offsets to -90.0
//   - spine faces backward → set offsets to +90.0
// If sensor is FLAT (horizontal) on a table → set to 0.0
//
// HOW TO CALIBRATE:
//   1. Sit in perfect upright posture with sensors mounted
//   2. Note the pitch values printed in Serial Monitor
//   3. Set TORSO_PITCH_OFFSET = -(that pitch value)
//      e.g. if it prints "-88.5°", set offset = 88.5
const float TORSO_PITCH_OFFSET = 90.0f;  // degrees to subtract from raw torso pitch
const float NECK_PITCH_OFFSET  = 90.0f;  // degrees to subtract from raw neck pitch

// ── Smoothing ───────────────────────────────────────────────
#define SMOOTH_N  4   // running average over N readings
struct SmoothBuf {
  float pitch[SMOOTH_N], roll[SMOOTH_N];
  int idx = 0;
  float avgPitch() { float s=0; for(int i=0;i<SMOOTH_N;i++) s+=pitch[i]; return s/SMOOTH_N; }
  float avgRoll()  { float s=0; for(int i=0;i<SMOOTH_N;i++) s+=roll[i];  return s/SMOOTH_N; }
};

SmoothBuf torsoSmooth, neckSmooth;

// ── Config ───────────────────────────────────────────────────
#define SERIAL_BAUD    115200
#define POST_INTERVAL  300    // ms between POSTs (matches frontend 200ms poll)
#define LED_PIN        2

// ── Buzzer ───────────────────────────────────────────────────
// Active buzzer: GPIO 25 → 100Ω resistor → Buzzer + → GND
// (Or direct if your buzzer is rated 3.3V)
#define BUZZER_PIN          25    // GPIO 25 — change if needed
#define BUZZ_TORSO_THRESH   40.0f // ° — torso pitch for "very bad" alert
#define BUZZ_NECK_THRESH    35.0f // ° — neck pitch for "very bad" alert
#define BUZZ_HOLD_MS        5000  // must stay bad for this long before buzzing
#define BUZZ_COOLDOWN_MS    10000 // minimum gap between buzz alerts

// ── Globals ──────────────────────────────────────────────────
bool torsoOk = false, neckOk = false;
unsigned long lastPost = 0;
int postCount = 0;
unsigned long badPostureStart = 0;   // when bad posture began
unsigned long lastBuzzTime    = 0;   // when we last buzzed
bool wasInBadPosture = false;
int lastFlexRaw = 0;   // raw ADC for Serial debug

// ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(500);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);  // buzzer off

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);

  // ADC for flex sensor
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);  // 0–3.3V range

  printBanner();

  // Scan I2C bus — shows exactly what's connected
  scanI2C();

  // Init MPUs
  torsoOk = initMPU(MPU_TORSO, "Torso (0x68)");
  neckOk  = initMPU(MPU_NECK,  "Neck  (0x69)");

  if (!torsoOk && !neckOk) {
    Serial.println("[ERROR] No MPU6050 found! Check wiring. Halting.");
    while (true) delay(1000);
  }

  // Connect WiFi
  connectWiFi();
}

// ─────────────────────────────────────────────────────────────
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Lost — reconnecting...");
    connectWiFi();
    return;
  }

  unsigned long now = millis();
  if (now - lastPost < POST_INTERVAL) return;
  lastPost = now;

  // ── Read sensors ─────────────────────────────────────────
  float tPitch = 0, tRoll = 0, nPitch = 0, nRoll = 0;

  if (torsoOk) {
    readMPU(MPU_TORSO, tPitch, tRoll);
    torsoSmooth.pitch[torsoSmooth.idx] = tPitch;
    torsoSmooth.roll[torsoSmooth.idx]  = tRoll;
    torsoSmooth.idx = (torsoSmooth.idx + 1) % SMOOTH_N;
    tPitch = torsoSmooth.avgPitch();
    tRoll  = torsoSmooth.avgRoll();
  }

  if (neckOk) {
    readMPU(MPU_NECK, nPitch, nRoll);
    neckSmooth.pitch[neckSmooth.idx] = nPitch;
    neckSmooth.roll[neckSmooth.idx]  = nRoll;
    neckSmooth.idx = (neckSmooth.idx + 1) % SMOOTH_N;
    nPitch = neckSmooth.avgPitch();
    nRoll  = neckSmooth.avgRoll();
  }

  // ── Apply mounting orientation offset ────────────────────
  // Raw pitch from accel assumes flat=0°.
  // Subtract offset so upright posture = ~0° when worn vertically.
  float tPitchAdj = tPitch - TORSO_PITCH_OFFSET;
  float nPitchAdj = nPitch - NECK_PITCH_OFFSET;

  // ── Read flex sensor ─────────────────────────────────────
  float flexPct = readFlex();

  // ── POST to backend ──────────────────────────────────────
  postCount++;
  bool ok = postData(tPitchAdj, tRoll, nPitchAdj, nRoll, flexPct);

  // Print to Serial Monitor
  Serial.printf("[#%d | T=%lus]\n", postCount, now / 1000);
  Serial.printf("  TORSO  raw=%+6.2f°  adjusted=%+6.2f°  roll=%+6.2f°\n", tPitch, tPitchAdj, tRoll);
  Serial.printf("  NECK   raw=%+6.2f°  adjusted=%+6.2f°  roll=%+6.2f°\n", nPitch, nPitchAdj, nRoll);
  Serial.printf("  FLEX   %.1f%% (raw ADC=%d)\n", flexPct, lastFlexRaw);
  Serial.printf("  POST   %s\n\n", ok ? "✅ HTTP 200" : "❌ FAILED");


  // ── Buzzer alert ─────────────────────────────────────────
  checkBuzzer(tPitchAdj, nPitchAdj, now);

  digitalWrite(LED_PIN, ok ? HIGH : LOW);
}

// ─────────────────────────────────────────────────────────────
// Buzz if posture is critically bad for more than BUZZ_HOLD_MS
void checkBuzzer(float tPitch, float nPitch, unsigned long now) {
  bool isBad = (abs(tPitch) > BUZZ_TORSO_THRESH) || (abs(nPitch) > BUZZ_NECK_THRESH);

  if (isBad) {
    if (!wasInBadPosture) {
      badPostureStart = now;
      wasInBadPosture = true;
    }
    if ((now - badPostureStart >= BUZZ_HOLD_MS) &&
        (now - lastBuzzTime   >= BUZZ_COOLDOWN_MS)) {
      lastBuzzTime = now;
      Serial.println("  [BUZZ] ⚠️  Bad posture alert!");
      buzzAlert();
    }
  } else {
    wasInBadPosture = false;  // reset when posture improves
  }
}

// 3 short beeps
void buzzAlert() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(150);
    digitalWrite(BUZZER_PIN, LOW);
    delay(100);
  }
}

// ─────────────────────────────────────────────────────────────
// Read flex sensor: 8-sample average, return 0–100% bend
float readFlex() {
  long sum = 0;
  for (int i = 0; i < 8; i++) {
    sum += analogRead(FLEX_PIN);
    delayMicroseconds(100);
  }
  lastFlexRaw = sum / 8;
  float pct = (float)(lastFlexRaw - FLEX_FLAT) / (float)(FLEX_BENT - FLEX_FLAT) * 100.0f;
  if (pct < 0.0f) pct = 0.0f;
  if (pct > 100.0f) pct = 100.0f;
  return pct;
}

// ─────────────────────────────────────────────────────────────
void readMPU(uint8_t addr, float& pitch, float& roll) {
  Wire.beginTransmission(addr);
  Wire.write(MPU_REG_ACCEL_XOUT_H);
  uint8_t err = Wire.endTransmission(true);  // true = release bus!
  if (err != 0) {
    Serial.printf("  [I2C ERR] endTransmission=%d for 0x%02X\n", err, addr);
    return;
  }

  uint8_t got = Wire.requestFrom((uint8_t)addr, (uint8_t)6);
  if (got != 6) {
    Serial.printf("  [I2C ERR] 0x%02X returned %d bytes (need 6)\n", addr, got);
    while (Wire.available()) Wire.read();
    return;
  }

  int16_t ax = (Wire.read() << 8) | Wire.read();
  int16_t ay = (Wire.read() << 8) | Wire.read();
  int16_t az = (Wire.read() << 8) | Wire.read();

  if (ax == -1 && ay == -1 && az == -1) {
    Serial.printf("  [I2C ERR] 0x%02X all 0xFF - not responding!\n", addr);
    return;
  }

  float axg = ax / 16384.0f;
  float ayg = ay / 16384.0f;
  float azg = az / 16384.0f;

  pitch = atan2(-axg, sqrt(ayg * ayg + azg * azg)) * 180.0f / PI;
  roll  = atan2( ayg, azg) * 180.0f / PI;
}

// ─────────────────────────────────────────────────────────────
bool postData(float tPitch, float tRoll, float nPitch, float nRoll, float flexPct) {
  StaticJsonDocument<256> doc;

  JsonObject torso = doc.createNestedObject("torso");
  torso["pitch"] = roundf(tPitch * 100) / 100.0f;
  torso["roll"]  = roundf(tRoll  * 100) / 100.0f;
  torso["yaw"]   = 0.0f;

  JsonObject neck = doc.createNestedObject("neck");
  neck["pitch"] = roundf(nPitch * 100) / 100.0f;
  neck["roll"]  = roundf(nRoll  * 100) / 100.0f;
  neck["yaw"]   = 0.0f;

  doc["flex_value"] = roundf(flexPct * 10) / 10.0f;
  doc["timestamp"]  = (long)millis();

  String payload;
  serializeJson(doc, payload);

  String url = String("http://") + BACKEND_IP + ":" + BACKEND_PORT + "/api/sensor-data";
  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(2000);

  int code = http.POST(payload);
  http.end();
  return (code == 200);
}

// ─────────────────────────────────────────────────────────────
bool initMPU(uint8_t addr, const char* label) {
  Wire.beginTransmission(addr);
  uint8_t err = Wire.endTransmission(true);  // true = release bus
  if (err != 0) {
    Serial.printf("[MPU] ❌ %s not found (err=%d)\n", label, err);
    return false;
  }
  // Wake up
  Wire.beginTransmission(addr);
  Wire.write(MPU_REG_PWR_MGMT_1);
  Wire.write(0x00);
  Wire.endTransmission(true);
  delay(100);

  // Verify read works
  Wire.beginTransmission(addr);
  Wire.write(MPU_REG_ACCEL_XOUT_H);
  Wire.endTransmission(true);
  uint8_t got = Wire.requestFrom((uint8_t)addr, (uint8_t)6);
  while (Wire.available()) Wire.read();  // flush

  if (got == 6) {
    Serial.printf("[MPU] ✅ %s ready (read OK)\n", label);
    return true;
  } else {
    Serial.printf("[MPU] ⚠️  %s found but read failed (%d bytes)\n", label, got);
    return false;
  }
}

// ─────────────────────────────────────────────────────────────
void scanI2C() {
  Serial.println("\n[I2C] Scanning bus...");
  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission(true) == 0) {
      found++;
      const char* h = "";
      if (a == 0x68) h = "  <-- MPU6050 Torso";
      if (a == 0x69) h = "  <-- MPU6050 Neck";
      Serial.printf("  0x%02X | Found%s\n", a, h);
    }
  }
  if (found == 0)
    Serial.println("  NO DEVICES FOUND! Check VCC/GND/SDA/SCL.");
  else
    Serial.printf("  %d device(s) on bus\n", found);
  Serial.println();
}

// ─────────────────────────────────────────────────────────────
void connectWiFi() {
  Serial.printf("\n[WiFi] Connecting to \"%s\"...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 60) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(LED_PIN, HIGH);
    Serial.printf("[WiFi] ✅ Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("[WiFi] Backend: http://%s:%d/api/sensor-data\n\n", BACKEND_IP, BACKEND_PORT);
  } else {
    Serial.printf("[WiFi] ❌ Failed (status=%d) — restarting in 5s\n", WiFi.status());
    delay(5000);
    ESP.restart();
  }
}

// ─────────────────────────────────────────────────────────────
void printBanner() {
  Serial.println();
  Serial.println("════════════════════════════════════════════════");
  Serial.println("  PoseGuide – Live Sensor Data");
  Serial.println("════════════════════════════════════════════════");
  Serial.println("  Torso MPU: 0x68 (AD0 → GND)");
  Serial.println("  Neck  MPU: 0x69 (AD0 → 3.3V)");
  Serial.println("  Flex sensor: GPIO 34 (1kΩ divider)");
  Serial.printf("  Buzzer: GPIO %d\n", BUZZER_PIN);
  Serial.printf("  POST interval: %dms\n", POST_INTERVAL);
  Serial.println("════════════════════════════════════════════════");
  Serial.println();
}
