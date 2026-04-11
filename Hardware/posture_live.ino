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

// ── Flex sensor (hardcoded — not connected) ──────────────
const float FLEX_VALUE = 30.0f;  // neutral spine curvature

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

// ── Globals ──────────────────────────────────────────────────
bool torsoOk = false, neckOk = false;
unsigned long lastPost = 0;
int postCount = 0;

// ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(500);
  pinMode(LED_PIN, OUTPUT);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);

  printBanner();

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

  // ── POST to backend ──────────────────────────────────────
  postCount++;
  bool ok = postData(tPitch, tRoll, nPitch, nRoll);

  // Print to Serial Monitor
  Serial.printf("[#%d | T=%lus]\n", postCount, now / 1000);
  Serial.printf("  TORSO  pitch=%+6.2f°  roll=%+6.2f°\n", tPitch, tRoll);
  Serial.printf("  NECK   pitch=%+6.2f°  roll=%+6.2f°\n", nPitch, nRoll);
  Serial.printf("  FLEX   %.1f (hardcoded)\n", FLEX_VALUE);
  Serial.printf("  POST   %s\n\n", ok ? "✅ HTTP 200" : "❌ FAILED");

  digitalWrite(LED_PIN, ok ? HIGH : LOW);
}

// ─────────────────────────────────────────────────────────────
void readMPU(uint8_t addr, float& pitch, float& roll) {
  Wire.beginTransmission(addr);
  Wire.write(MPU_REG_ACCEL_XOUT_H);
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)addr, (uint8_t)6);  // 6 bytes = accel only

  int16_t ax = (Wire.read() << 8) | Wire.read();
  int16_t ay = (Wire.read() << 8) | Wire.read();
  int16_t az = (Wire.read() << 8) | Wire.read();

  float axg = ax / 16384.0f;
  float ayg = ay / 16384.0f;
  float azg = az / 16384.0f;

  pitch = atan2(-axg, sqrt(ayg * ayg + azg * azg)) * 180.0f / PI;
  roll  = atan2( ayg, azg) * 180.0f / PI;
}

// ─────────────────────────────────────────────────────────────
bool postData(float tPitch, float tRoll, float nPitch, float nRoll) {
  StaticJsonDocument<256> doc;

  JsonObject torso = doc.createNestedObject("torso");
  torso["pitch"] = roundf(tPitch * 100) / 100.0f;
  torso["roll"]  = roundf(tRoll  * 100) / 100.0f;
  torso["yaw"]   = 0.0f;

  JsonObject neck = doc.createNestedObject("neck");
  neck["pitch"] = roundf(nPitch * 100) / 100.0f;
  neck["roll"]  = roundf(nRoll  * 100) / 100.0f;
  neck["yaw"]   = 0.0f;

  doc["flex_value"] = FLEX_VALUE;
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
  Wire.write(MPU_REG_PWR_MGMT_1);
  if (Wire.endTransmission(false) != 0) {
    Serial.printf("[MPU] ❌ %s not found\n", label);
    return false;
  }
  // Wake up
  Wire.beginTransmission(addr);
  Wire.write(MPU_REG_PWR_MGMT_1);
  Wire.write(0x00);
  Wire.endTransmission();
  delay(100);
  Serial.printf("[MPU] ✅ %s ready\n", label);
  return true;
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
  Serial.println("  Flex sensor: hardcoded at 30.0");
  Serial.printf("  POST interval: %dms\n", POST_INTERVAL);
  Serial.println("════════════════════════════════════════════════");
  Serial.println();
}
