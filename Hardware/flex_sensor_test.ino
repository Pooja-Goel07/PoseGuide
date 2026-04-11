/*
 * ═══════════════════════════════════════════════════════════
 *  PoseGuide – Flex Sensor Test (Direct ESP32 ADC)
 *  File: Hardware/flex_sensor_test.ino
 * ═══════════════════════════════════════════════════════════
 *
 *  No ADS1115 needed. Reads flex sensor directly via ESP32
 *  built-in 12-bit ADC. Uses averaging to reduce noise.
 *
 *  WIRING — Voltage Divider:
 *
 *    3.3V ──── Flex Sensor leg 1
 *              Flex Sensor leg 2 ──┬──── GPIO 34
 *                                  │
 *                               1kΩ resistor
 *                                  │
 *    GND ────────────────────────────
 *
 *  GPIO 34 is ADC1 — safe to use alongside WiFi.
 *  DO NOT use ADC2 pins (GPIO 0,2,4,12-15,25-27) — they
 *  conflict with WiFi and give garbage readings.
 *
 *  HOW THE FLEX SENSOR WORKS:
 *    Flat  → low resistance  → higher voltage at GPIO 34 → high ADC value
 *    Bent  → high resistance → lower voltage at GPIO 34  → low ADC value
 *
 *  12-bit ADC range: 0 to 4095
 *  3.3V supply → 1 LSB ≈ 0.806mV
 *
 *  WHAT THIS SKETCH DOES:
 *    1. Reads GPIO 34 with 32-sample averaging (reduces noise)
 *    2. Prints raw ADC, voltage, and 0–100% bend estimate
 *    3. Shows a live bar graph of bending
 *    4. Tracks min/max so you can calibrate FLAT and BENT values
 * ═══════════════════════════════════════════════════════════
 */

// ── Pin ────────────────────────────────────────────────────
#define FLEX_PIN    34        // ADC1 channel 6 — input only, WiFi safe

// ── Calibration ────────────────────────────────────────────
// Run the sketch first, note the values:
//   FLAT_RAW = ADC reading when sensor is STRAIGHT (not bent)
//   BENT_RAW = ADC reading when sensor is FULLY BENT
// With 1kΩ pull-down the ADC range is small (~60–370 counts).
// Values below are estimates — the [CAL] hint will give you exact numbers.
int FLAT_RAW = 370;    // typical FLAT with 1kΩ  (~0.30V)
int BENT_RAW =  60;    // typical BENT with 1kΩ  (~0.05V)

// ── Config ─────────────────────────────────────────────────
#define SERIAL_BAUD     115200
#define READ_INTERVAL   300     // ms between readings
#define AVG_SAMPLES     32      // number of samples to average (reduces noise)

// ── Globals ─────────────────────────────────────────────────
unsigned long lastRead = 0;
int minSeen = 4095;
int maxSeen = 0;

// ──────────────────────────────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(500);

  // ESP32 ADC setup
  analogReadResolution(12);        // 12-bit: 0–4095
  analogSetAttenuation(ADC_11db);  // 0–3.3V range

  printBanner();
}

// ──────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();
  if (now - lastRead < READ_INTERVAL) return;
  lastRead = now;

  // Average multiple samples to reduce ESP32 ADC noise
  long sum = 0;
  for (int i = 0; i < AVG_SAMPLES; i++) {
    sum += analogRead(FLEX_PIN);
    delayMicroseconds(100);
  }
  int raw = sum / AVG_SAMPLES;

  // Track min/max for calibration
  if (raw < minSeen) minSeen = raw;
  if (raw > maxSeen) maxSeen = raw;

  // Convert to voltage (12-bit, 3.3V reference)
  float voltage = raw * (3.3f / 4095.0f);

  // Compute bend %: FLAT = 0%, BENT = 100%
  float bend = mapFloat(raw, FLAT_RAW, BENT_RAW, 0.0f, 100.0f);
  bend = constrain(bend, 0.0f, 100.0f);

  // Print row
  Serial.printf("[T=%4lus]  Raw: %4d   Voltage: %.3fV   Bend: %5.1f%%   ",
    now / 1000, raw, voltage, bend);
  printBar(bend, 28);

  // Every 10 seconds, print calibration hint
  static unsigned long lastCalPrint = 0;
  if (now - lastCalPrint > 10000) {
    lastCalPrint = now;
    Serial.println();
    Serial.println("  ─── CALIBRATION HINT ───────────────────────────");
    Serial.printf("  Session max (keep flat) : %d  → use as FLAT_RAW\n", maxSeen);
    Serial.printf("  Session min (bend fully): %d  → use as BENT_RAW\n", minSeen);
    Serial.println("  Update FLAT_RAW and BENT_RAW at top of this file.");
    Serial.println("  ─────────────────────────────────────────────────");
    Serial.println();
  }
}

// ──────────────────────────────────────────────────────────
void printBar(float percent, int width) {
  int filled = (int)(percent / 100.0f * width);
  filled = constrain(filled, 0, width);

  Serial.print("[");
  for (int i = 0; i < width; i++) {
    Serial.print(i < filled ? "█" : "░");
  }
  Serial.print("]");

  if      (percent < 15.0f) Serial.println("  FLAT");
  else if (percent < 40.0f) Serial.println("  SLIGHT BEND");
  else if (percent < 70.0f) Serial.println("  MODERATE BEND");
  else                       Serial.println("  FULLY BENT ⚠️");
}

// ──────────────────────────────────────────────────────────
float mapFloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

// ──────────────────────────────────────────────────────────
void printBanner() {
  Serial.println();
  Serial.println("═══════════════════════════════════════════════════");
  Serial.println("  PoseGuide – Flex Sensor Test (Direct ADC)");
  Serial.println("═══════════════════════════════════════════════════");
  Serial.println("  No library needed. Uses ESP32 built-in ADC.");
  Serial.println("  Flex Sensor → GPIO 34  (ADC1, WiFi-safe)");
  Serial.println("  Voltage divider: 3.3V → Flex → GPIO34 → 1kΩ → GND");
  Serial.println("═══════════════════════════════════════════════════");
  Serial.println();
  Serial.printf("  Calibration: FLAT_RAW=%d  BENT_RAW=%d\n", FLAT_RAW, BENT_RAW);
  Serial.println("  Bend/flatten the sensor to calibrate. Min/max printed every 10s.");
  Serial.println();
}
