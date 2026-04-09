/*
 * PoseGuide – ESP32 Configuration
 * ────────────────────────────────
 * Update these values before uploading to your ESP32.
 */

#ifndef CONFIG_H
#define CONFIG_H

// ── Wi-Fi Credentials ──────────────────────────────────
#define WIFI_SSID       "YOUR_WIFI_SSID"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"

// ── Backend Server ─────────────────────────────────────
// IP address of the machine running the FastAPI backend
#define SERVER_HOST     "192.168.1.100"
#define SERVER_PORT     8000
#define WS_PATH         "/ws/esp32"

// ── I2C Addresses ──────────────────────────────────────
// MPU #1 (T4 – upper back) → AD0 = LOW  → 0x68
// MPU #2 (C7 – neck)       → AD0 = HIGH → 0x69
#define MPU1_ADDRESS    0x68
#define MPU2_ADDRESS    0x69

// ADS1115 default I2C address
#define ADS1115_ADDRESS 0x48

// ── Sensor Fusion ──────────────────────────────────────
// Madgwick filter gain (beta) – higher = faster convergence but more noise
#define MADGWICK_BETA   0.1f

// Sampling rate in Hz
#define SAMPLE_RATE_HZ  50
#define SAMPLE_PERIOD_MS (1000 / SAMPLE_RATE_HZ)

// ── Flex Sensor ────────────────────────────────────────
// ADS1115 channel connected to flex sensor
#define FLEX_ADS_CHANNEL    0

// Calibration: flat = ~300, fully bent = ~800 (adjust per your sensor)
#define FLEX_FLAT_VALUE     300.0f
#define FLEX_BENT_VALUE     800.0f

#endif // CONFIG_H
