/*
 * ═══════════════════════════════════════════════════════════
 *  PoseGuide – Dual MPU6050 Test
 *  File: Hardware/mpu6050_test.ino
 * ═══════════════════════════════════════════════════════════
 *
 *  Tests BOTH MPU6050 sensors over I2C.
 *  No WiFi or extra libraries needed — uses Wire.h only.
 *
 *  WIRING (both MPUs share the same SDA/SCL lines):
 *
 *    ESP32 3.3V  ──┬── MPU #1 VCC      ── MPU #2 VCC
 *    ESP32 GND   ──┼── MPU #1 GND      ── MPU #2 GND
 *    ESP32 GPIO21──┼── MPU #1 SDA      ── MPU #2 SDA
 *    ESP32 GPIO22──┼── MPU #1 SCL      ── MPU #2 SCL
 *                  │
 *    ESP32 GND   ──┘── MPU #1 AD0  (address = 0x68, T4 torso)
 *    ESP32 3.3V  ────── MPU #2 AD0  (address = 0x69, C7 neck)
 *
 *  AD0 = GND  →  I2C address 0x68
 *  AD0 = 3.3V →  I2C address 0x69
 *
 *  What this sketch does:
 *    1. Scans I2C bus and reports what's found
 *    2. Initialises both MPUs (wakes them from sleep mode)
 *    3. Prints raw accel + gyro values every 500ms
 *    4. Computes simple pitch & roll from accelerometer
 *    5. Warns if a sensor is missing or returning bad data
 * ═══════════════════════════════════════════════════════════
 */

#include <Wire.h>

// ── I2C Pins (ESP32 default) ───────────────────────────────
#define SDA_PIN  21
#define SCL_PIN  22

// ── MPU6050 I2C Addresses ──────────────────────────────────
#define MPU_TORSO  0x68   // AD0 → GND  (T4, lower back sensor)
#define MPU_NECK   0x69   // AD0 → 3.3V (C7, neck/upper back sensor)

// ── MPU6050 Register Addresses ────────────────────────────
#define MPU_REG_PWR_MGMT_1   0x6B
#define MPU_REG_ACCEL_XOUT_H 0x3B
#define MPU_REG_WHO_AM_I     0x75
#define MPU_EXPECTED_WHOAMI  0x68   // WHO_AM_I always returns 0x68 regardless of AD0

// ── Config ─────────────────────────────────────────────────
#define SERIAL_BAUD   115200
#define READ_INTERVAL 500    // ms between readings

// ── Sensor raw data struct ─────────────────────────────────
struct MPUData {
  int16_t ax, ay, az;   // accelerometer raw (±2g range → ÷16384 = g)
  int16_t gx, gy, gz;   // gyroscope raw (±250°/s range → ÷131 = °/s)
  float pitch, roll;     // computed from accel (tilt angles in degrees)
  bool   ok;             // false if sensor not responding
};

// ── Globals ─────────────────────────────────────────────────
bool torsoOk = false;
bool neckOk  = false;
unsigned long lastRead = 0;

// ──────────────────────────────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(500);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);   // 400kHz Fast Mode

  printBanner();

  // ── I2C Bus Scan ───────────────────────────────────────
  scanI2C();

  // ── Initialise sensors ────────────────────────────────
  torsoOk = initMPU(MPU_TORSO, "Torso (0x68)");
  neckOk  = initMPU(MPU_NECK,  "Neck  (0x69)");

  Serial.println();
  Serial.println("─────────────────────────────────────────────────────");
  Serial.printf("  Torso MPU : %s\n", torsoOk ? "✅ FOUND & READY" : "❌ NOT FOUND");
  Serial.printf("  Neck  MPU : %s\n", neckOk  ? "✅ FOUND & READY" : "❌ NOT FOUND");
  Serial.println("─────────────────────────────────────────────────────");

  if (!torsoOk && !neckOk) {
    Serial.println("\n  Both sensors missing! Check wiring:");
    Serial.println("  - VCC → 3.3V (not 5V)");
    Serial.println("  - SDA → GPIO 21");
    Serial.println("  - SCL → GPIO 22");
    Serial.println("  - AD0 → GND for 0x68, 3.3V for 0x69");
    Serial.println("  Halting.");
    while (true) delay(1000);
  }

  Serial.println("\n  Reading every 500ms. Tilt the sensors to see values change.\n");
  Serial.println("  FORMAT:  Pitch = forward/back tilt   Roll = side tilt");
  Serial.println("  GOOD posture: both sensors near 0°\n");
}

// ──────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();
  if (now - lastRead < READ_INTERVAL) return;
  lastRead = now;

  MPUData torso = {}, neck = {};

  if (torsoOk) {
    torso = readMPU(MPU_TORSO);
    torso.ok = true;
  }
  if (neckOk) {
    neck = readMPU(MPU_NECK);
    neck.ok = true;
  }

  // ── Print formatted table ──────────────────────────────
  Serial.printf("\n[T=%lus]\n", now / 1000);

  printMPURow("TORSO (0x68)", torso, torsoOk);
  printMPURow("NECK  (0x69)", neck,  neckOk);

  // ── Warn if values look frozen (all zeros = bad connection) ──
  if (torsoOk && torso.ax == 0 && torso.ay == 0 && torso.az == 0) {
    Serial.println("  ⚠️  Torso: all zeros — check SDA/SCL wiring");
  }
  if (neckOk && neck.ax == 0 && neck.ay == 0 && neck.az == 0) {
    Serial.println("  ⚠️  Neck:  all zeros — check SDA/SCL wiring");
  }
}

// ──────────────────────────────────────────────────────────
bool initMPU(uint8_t addr, const char* label) {
  Serial.printf("\n  Initialising %s...\n", label);

  // Check WHO_AM_I register
  Wire.beginTransmission(addr);
  Wire.write(MPU_REG_WHO_AM_I);
  if (Wire.endTransmission(false) != 0) {
    Serial.printf("  ❌ %s: No I2C ACK — not connected\n", label);
    return false;
  }
  Wire.requestFrom((uint8_t)addr, (uint8_t)1);
  uint8_t whoami = Wire.read();
  Serial.printf("  WHO_AM_I = 0x%02X (expected 0x68) %s\n",
    whoami, whoami == MPU_EXPECTED_WHOAMI ? "✅" : "⚠️ unexpected");

  // Wake up: write 0 to PWR_MGMT_1 (clears sleep bit)
  writeReg(addr, MPU_REG_PWR_MGMT_1, 0x00);
  delay(100);

  // Confirm it's awake by reading the register back
  uint8_t pwr = readReg(addr, MPU_REG_PWR_MGMT_1);
  if (pwr == 0x00) {
    Serial.printf("  PWR_MGMT_1 = 0x%02X ✅ (awake)\n", pwr);
    return true;
  } else {
    Serial.printf("  PWR_MGMT_1 = 0x%02X ⚠️ (check sensor)\n", pwr);
    return false;
  }
}

// ──────────────────────────────────────────────────────────
MPUData readMPU(uint8_t addr) {
  MPUData d;

  Wire.beginTransmission(addr);
  Wire.write(MPU_REG_ACCEL_XOUT_H);
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)addr, (uint8_t)14);  // 14 bytes: accel + temp + gyro

  d.ax = (Wire.read() << 8) | Wire.read();
  d.ay = (Wire.read() << 8) | Wire.read();
  d.az = (Wire.read() << 8) | Wire.read();
  Wire.read(); Wire.read();  // skip temperature

  d.gx = (Wire.read() << 8) | Wire.read();
  d.gy = (Wire.read() << 8) | Wire.read();
  d.gz = (Wire.read() << 8) | Wire.read();

  // Convert to g (±2g range)
  float ax_g = d.ax / 16384.0f;
  float ay_g = d.ay / 16384.0f;
  float az_g = d.az / 16384.0f;

  // Simple tilt angles from accelerometer (works when sensor is relatively still)
  d.pitch = atan2(-ax_g, sqrt(ay_g * ay_g + az_g * az_g)) * 180.0f / PI;
  d.roll  = atan2( ay_g, az_g) * 180.0f / PI;

  return d;
}

// ──────────────────────────────────────────────────────────
void printMPURow(const char* label, MPUData& d, bool active) {
  if (!active) {
    Serial.printf("  %-12s  ❌ NOT CONNECTED\n", label);
    return;
  }

  // Accel in g (÷16384 for ±2g range)
  float ax = d.ax / 16384.0f;
  float ay = d.ay / 16384.0f;
  float az = d.az / 16384.0f;

  // Gyro in °/s (÷131 for ±250°/s range)
  float gx = d.gx / 131.0f;
  float gy = d.gy / 131.0f;
  float gz = d.gz / 131.0f;

  Serial.printf("  %-12s  Pitch=%+7.2f°  Roll=%+7.2f°\n",
    label, d.pitch, d.roll);
  Serial.printf("    Accel: X=%+6.3fg  Y=%+6.3fg  Z=%+6.3fg\n", ax, ay, az);
  Serial.printf("    Gyro:  X=%+7.2f°/s  Y=%+7.2f°/s  Z=%+7.2f°/s\n", gx, gy, gz);
}

// ──────────────────────────────────────────────────────────
void scanI2C() {
  Serial.println("[I2C] Scanning bus (GPIO21=SDA, GPIO22=SCL)...\n");
  Serial.println("      Addr | Status");
  Serial.println("      -----|-------");

  int found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      found++;
      const char* hint = "";
      if (addr == 0x68) hint = "  ← MPU6050 #1 (AD0=GND)  ✅";
      if (addr == 0x69) hint = "  ← MPU6050 #2 (AD0=3.3V) ✅";
      if (addr == 0x48) hint = "  ← ADS1115";
      Serial.printf("      0x%02X | Found%s\n", addr, hint);
    }
  }

  if (found == 0) {
    Serial.println("      No devices found! Check 3.3V, GND, SDA, SCL wiring.");
  } else {
    Serial.printf("\n      Found %d device(s) on I2C bus.\n", found);

    if (found == 1) {
      Serial.println("      ⚠️  Only 1 MPU found — check AD0 pin on missing sensor.");
    }
    if (found >= 2) {
      Serial.println("      ✅  Both MPUs detected.");
    }
  }
}

// ──────────────────────────────────────────────────────────
void writeReg(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

uint8_t readReg(uint8_t addr, uint8_t reg) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)addr, (uint8_t)1);
  return Wire.read();
}

// ──────────────────────────────────────────────────────────
void printBanner() {
  Serial.println();
  Serial.println("═══════════════════════════════════════════════════");
  Serial.println("  PoseGuide – Dual MPU6050 Sensor Test");
  Serial.println("═══════════════════════════════════════════════════");
  Serial.println("  No WiFi needed. Uses Wire.h only.");
  Serial.println("  SDA → GPIO 21   SCL → GPIO 22");
  Serial.println("  MPU #1 (Torso): AD0 → GND  → address 0x68");
  Serial.println("  MPU #2 (Neck) : AD0 → 3.3V → address 0x69");
  Serial.println("═══════════════════════════════════════════════════");
  Serial.println();
}
