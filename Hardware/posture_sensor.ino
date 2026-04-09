/*
 * ╔══════════════════════════════════════════════════════════╗
 * ║  PoseGuide – ESP32 Posture Sensor Firmware               ║
 * ║  Real-Time Posture Detection & Feedback System            ║
 * ╠══════════════════════════════════════════════════════════╣
 * ║  Reads 2× MPU-6050 IMU + 1× Flex sensor via ADS1115     ║
 * ║  Applies Madgwick sensor fusion filter                    ║
 * ║  Sends JSON over WebSocket to FastAPI backend             ║
 * ╚══════════════════════════════════════════════════════════╝
 *
 * Required Libraries (install via Arduino Library Manager):
 *   - WiFi              (built-in with ESP32 board package)
 *   - Wire              (built-in)
 *   - ArduinoWebsockets (by Gil Maimon)
 *   - ArduinoJson       (by Benoit Blanchon, v7+)
 *   - Adafruit ADS1X15  (by Adafruit)
 *   - MadgwickAHRS      (by Arduino)
 */

#include <WiFi.h>
#include <Wire.h>
#include <ArduinoWebsockets.h>
#include <ArduinoJson.h>
#include <Adafruit_ADS1X15.h>
#include <MadgwickAHRS.h>
#include "config.h"

using namespace websockets;

// ── Objects ────────────────────────────────────────────────
WebsocketsClient wsClient;
Adafruit_ADS1115 ads;
Madgwick filterMPU1;
Madgwick filterMPU2;

// ── Sensor Data ────────────────────────────────────────────
float ax1, ay1, az1, gx1, gy1, gz1;  // MPU #1 raw
float ax2, ay2, az2, gx2, gy2, gz2;  // MPU #2 raw

// ── Timing ─────────────────────────────────────────────────
unsigned long lastSampleTime = 0;
unsigned long lastReconnectAttempt = 0;
const unsigned long RECONNECT_INTERVAL = 5000;

// ── Status LED ─────────────────────────────────────────────
#define STATUS_LED 2  // Built-in LED on most ESP32 dev boards

// ════════════════════════════════════════════════════════════
//  SETUP
// ════════════════════════════════════════════════════════════
void setup() {
    Serial.begin(115200);
    delay(100);

    pinMode(STATUS_LED, OUTPUT);
    digitalWrite(STATUS_LED, LOW);

    Serial.println();
    Serial.println("╔═══════════════════════════════════╗");
    Serial.println("║   PoseGuide Sensor Initializing   ║");
    Serial.println("╚═══════════════════════════════════╝");

    // ── I2C ────────────────────────────────────────────
    Wire.begin();
    Wire.setClock(400000);  // 400kHz fast mode

    // ── MPU-6050 #1 (T4 – Upper Back) ──────────────────
    initMPU(MPU1_ADDRESS);
    Serial.println("✓ MPU #1 (T4 upper back) initialized");

    // ── MPU-6050 #2 (C7 – Neck) ───────────────────────
    initMPU(MPU2_ADDRESS);
    Serial.println("✓ MPU #2 (C7 neck) initialized");

    // ── ADS1115 (Flex Sensor ADC) ─────────────────────
    if (ads.begin(ADS1115_ADDRESS)) {
        ads.setGain(GAIN_ONE);  // ±4.096V range
        Serial.println("✓ ADS1115 initialized");
    } else {
        Serial.println("✗ ADS1115 not found – flex sensor disabled");
    }

    // ── Madgwick Filters ──────────────────────────────
    filterMPU1.begin(SAMPLE_RATE_HZ);
    filterMPU2.begin(SAMPLE_RATE_HZ);
    Serial.println("✓ Madgwick filters initialized");

    // ── Wi-Fi ─────────────────────────────────────────
    connectWiFi();

    // ── WebSocket ─────────────────────────────────────
    connectWebSocket();

    Serial.println("─── Entering main loop ───");
    Serial.println();
}

// ════════════════════════════════════════════════════════════
//  MAIN LOOP
// ════════════════════════════════════════════════════════════
void loop() {
    unsigned long now = millis();

    // ── Reconnect WebSocket if needed ──────────────────
    if (!wsClient.available()) {
        if (now - lastReconnectAttempt > RECONNECT_INTERVAL) {
            lastReconnectAttempt = now;
            Serial.println("↻ Reconnecting WebSocket...");
            connectWebSocket();
        }
        delay(100);
        return;
    }

    // ── Sample at fixed rate ──────────────────────────
    if (now - lastSampleTime < SAMPLE_PERIOD_MS) {
        wsClient.poll();
        return;
    }
    lastSampleTime = now;

    // ── Read MPU #1 ───────────────────────────────────
    readMPU(MPU1_ADDRESS, ax1, ay1, az1, gx1, gy1, gz1);
    filterMPU1.updateIMU(gx1, gy1, gz1, ax1, ay1, az1);

    // ── Read MPU #2 ───────────────────────────────────
    readMPU(MPU2_ADDRESS, ax2, ay2, az2, gx2, gy2, gz2);
    filterMPU2.updateIMU(gx2, gy2, gz2, ax2, ay2, az2);

    // ── Read Flex Sensor ──────────────────────────────
    int16_t flexRaw = ads.readADC_SingleEnded(FLEX_ADS_CHANNEL);
    float flexValue = mapFloat(flexRaw, FLEX_FLAT_VALUE, FLEX_BENT_VALUE, 0.0, 100.0);
    flexValue = constrain(flexValue, 0.0, 100.0);

    // ── Build JSON Packet ─────────────────────────────
    JsonDocument doc;

    JsonObject torso = doc["torso"].to<JsonObject>();
    torso["pitch"] = round2(filterMPU1.getPitch());
    torso["roll"]  = round2(filterMPU1.getRoll());
    torso["yaw"]   = round2(filterMPU1.getYaw());

    JsonObject neck = doc["neck"].to<JsonObject>();
    neck["pitch"] = round2(filterMPU2.getPitch());
    neck["roll"]  = round2(filterMPU2.getRoll());
    neck["yaw"]   = round2(filterMPU2.getYaw());

    doc["flex_value"] = round2(flexValue);
    doc["timestamp"]  = (double)now;

    // ── Serialize & Send ──────────────────────────────
    String jsonStr;
    serializeJson(doc, jsonStr);
    wsClient.send(jsonStr);

    // ── Blink LED on successful send ──────────────────
    digitalWrite(STATUS_LED, HIGH);
    delay(2);
    digitalWrite(STATUS_LED, LOW);

    wsClient.poll();
}

// ════════════════════════════════════════════════════════════
//  HELPER FUNCTIONS
// ════════════════════════════════════════════════════════════

void connectWiFi() {
    Serial.printf("Connecting to Wi-Fi: %s", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println();
        Serial.printf("✓ Wi-Fi connected │ IP: %s\n", WiFi.localIP().toString().c_str());
        digitalWrite(STATUS_LED, HIGH);
        delay(200);
        digitalWrite(STATUS_LED, LOW);
    } else {
        Serial.println("\n✗ Wi-Fi connection failed – restarting...");
        ESP.restart();
    }
}

void connectWebSocket() {
    char url[128];
    snprintf(url, sizeof(url), "ws://%s:%d%s", SERVER_HOST, SERVER_PORT, WS_PATH);
    Serial.printf("Connecting WebSocket: %s\n", url);

    bool connected = wsClient.connect(url);
    if (connected) {
        Serial.println("✓ WebSocket connected");
    } else {
        Serial.println("✗ WebSocket connection failed");
    }
}

void initMPU(uint8_t address) {
    // Wake up MPU-6050
    Wire.beginTransmission(address);
    Wire.write(0x6B);  // PWR_MGMT_1
    Wire.write(0x00);  // Wake up
    Wire.endTransmission(true);
    delay(10);

    // Configure gyroscope: ±500°/s
    Wire.beginTransmission(address);
    Wire.write(0x1B);  // GYRO_CONFIG
    Wire.write(0x08);  // FS_SEL = 1 (±500°/s)
    Wire.endTransmission(true);

    // Configure accelerometer: ±4g
    Wire.beginTransmission(address);
    Wire.write(0x1C);  // ACCEL_CONFIG
    Wire.write(0x08);  // AFS_SEL = 1 (±4g)
    Wire.endTransmission(true);

    // Set DLPF bandwidth: 44Hz
    Wire.beginTransmission(address);
    Wire.write(0x1A);  // CONFIG
    Wire.write(0x03);  // DLPF_CFG = 3
    Wire.endTransmission(true);
}

void readMPU(uint8_t address, float &ax, float &ay, float &az,
             float &gx, float &gy, float &gz) {
    Wire.beginTransmission(address);
    Wire.write(0x3B);  // ACCEL_XOUT_H
    Wire.endTransmission(false);
    Wire.requestFrom(address, (uint8_t)14, (uint8_t)true);

    int16_t rawAx = (Wire.read() << 8) | Wire.read();
    int16_t rawAy = (Wire.read() << 8) | Wire.read();
    int16_t rawAz = (Wire.read() << 8) | Wire.read();
    Wire.read(); Wire.read();  // Skip temperature
    int16_t rawGx = (Wire.read() << 8) | Wire.read();
    int16_t rawGy = (Wire.read() << 8) | Wire.read();
    int16_t rawGz = (Wire.read() << 8) | Wire.read();

    // Convert to physical units
    // Accel: ±4g → sensitivity = 8192 LSB/g
    ax = rawAx / 8192.0f;
    ay = rawAy / 8192.0f;
    az = rawAz / 8192.0f;

    // Gyro: ±500°/s → sensitivity = 65.5 LSB/(°/s)
    gx = rawGx / 65.5f;
    gy = rawGy / 65.5f;
    gz = rawGz / 65.5f;
}

float mapFloat(float x, float inMin, float inMax, float outMin, float outMax) {
    return (x - inMin) * (outMax - outMin) / (inMax - inMin) + outMin;
}

float round2(float val) {
    return roundf(val * 100.0f) / 100.0f;
}
