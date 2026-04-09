# PoseGuide – Hardware Setup Guide

## Components Required

| Component | Quantity | Purpose |
|-----------|----------|---------|
| ESP32 Dev Board | 1 | Microcontroller with Wi-Fi |
| MPU-6050 IMU | 2 | Orientation sensing (upper back + neck) |
| Flex Sensor | 1 | Spinal curvature measurement |
| ADS1115 ADC | 1 | High-resolution analog-to-digital conversion |
| 10kΩ Resistor | 1 | Voltage divider for flex sensor |
| Elastic Band / Vest | 1 | Body-mounting mechanism |

## Wiring Diagram

```
ESP32                    MPU-6050 #1 (T4)       MPU-6050 #2 (C7)
┌─────────┐              ┌──────────┐            ┌──────────┐
│     3V3 ├──────────────┤ VCC      │       ┌────┤ VCC      │
│     GND ├──────────────┤ GND      │       │    │ GND ─────│── GND
│  GPIO21 ├──── SDA ─────┤ SDA      │       │    │ SDA ─────│── SDA (shared)
│  GPIO22 ├──── SCL ─────┤ SCL      │       │    │ SCL ─────│── SCL (shared)
│         │              │ AD0 → GND│(0x68) │    │ AD0 → 3V3│(0x69)
└─────────┘              └──────────┘       │    └──────────┘
                                            │
                          ADS1115            │
                         ┌──────────┐        │
                    3V3 ─┤ VCC      │────────┘
                    GND ─┤ GND      │
               SDA(21) ─┤ SDA      │  (shared I2C bus)
               SCL(22) ─┤ SCL      │
                         │ A0  ◄────│── Flex sensor voltage divider
                         └──────────┘

Flex Sensor Circuit:
  3V3 ──┤ Flex Sensor ├──┬── ADS1115 A0
                         │
                        [10kΩ]
                         │
                        GND
```

## I2C Addresses

| Device | Address | AD0 Pin |
|--------|---------|---------|
| MPU #1 (T4 upper back) | `0x68` | Connected to GND |
| MPU #2 (C7 neck) | `0x69` | Connected to 3V3 |
| ADS1115 | `0x48` | Default (ADDR → GND) |

## Sensor Placement on Body

```
        ┌─── Head ───┐
        │             │
        └──────┬──────┘
               │
          ╔════╧════╗  ← MPU #2 (C7 vertebra – neck base)
          ║         ║
          ║  Flex   ║  ← Flex sensor runs along spine
          ║  Sensor ║
          ║         ║
          ╠═════════╣  ← MPU #1 (T4 vertebra – upper back)
          ║         ║
          ║  Torso  ║
          ║         ║
          ╚═════════╝
```

## Required Arduino Libraries

Install via **Arduino IDE → Library Manager**:

1. **ArduinoWebsockets** by Gil Maimon
2. **ArduinoJson** by Benoit Blanchon (v7+)
3. **Adafruit ADS1X15** by Adafruit
4. **MadgwickAHRS** by Arduino

## ESP32 Board Setup

1. Open **Arduino IDE → Preferences**
2. Add to Board Manager URLs:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Open **Tools → Board → Board Manager** → Search **ESP32** → Install
4. Select board: **ESP32 Dev Module**

## Configuration

Edit `config.h` before uploading:

```cpp
#define WIFI_SSID       "YourWiFiName"
#define WIFI_PASSWORD   "YourWiFiPassword"
#define SERVER_HOST     "192.168.1.100"  // Your PC's local IP
```

## Upload

1. Connect ESP32 via USB
2. Select correct **COM port** in Arduino IDE
3. Click **Upload**
4. Open **Serial Monitor** (115200 baud) to verify connection
