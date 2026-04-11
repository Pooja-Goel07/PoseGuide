# PoseGuide – Setup & Run Instructions

> Complete step-by-step commands to set up and run all three subsystems.

---

## Prerequisites

| Tool | Version | Check Command |
|------|---------|---------------|
| **Node.js** | v18+ | `node --version` |
| **npm** | v9+ | `npm --version` |
| **Python** | 3.10+ | `python --version` |S
| **pip** | latest | `pip --version` |
| **Arduino IDE** | 2.x | — |

---

## 1. Frontend Setup (React + TypeScript)

```bash
# Navigate to frontend directory
cd frontend

# Install all dependencies (Three.js, Recharts, React Router, etc.)
npm install

# Start the development server (opens at http://localhost:3000)
npm start
```

### What you'll see:
- The dashboard loads in **Demo Mode** with simulated sensor data
- A 3D human model animates automatically to showcase posture feedback
- All charts and gauges update in real-time with demo data
- Connect the backend + ESP32 to switch to **Live Mode**

---

## 2. Backend Setup (FastAPI + Python)

```bash
# Navigate to backend directory
cd Backend

# Create a virtual environment (if not already created)
python -m venv venv

# Activate the virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# On Windows (Command Prompt):
.\venv\Scripts\activate.bat

# On macOS/Linux:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI server
python main.py
```

### Alternatively, run with uvicorn directly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Verify the backend:
- Health check: [http://localhost:8000/health](http://localhost:8000/health)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Latest data: [http://localhost:8000/api/latest](http://localhost:8000/api/latest)

### WebSocket Endpoints:
| Endpoint | Purpose |
|----------|---------|
| `ws://localhost:8000/ws/esp32` | ESP32 hardware sends sensor data here |
| `ws://localhost:8000/ws/dashboard` | React dashboard connects here to receive data |

---

## 3. Hardware Setup (ESP32 + Dual MPU6050)

### Step 1 — Install ESP32 Board Support in Arduino IDE

1. **File → Preferences** → paste into "Additional Board Manager URLs":
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
2. **Tools → Board → Board Manager** → search "ESP32" → Install **esp32 by Espressif Systems**
3. **Tools → Board → ESP32 Dev Module**
4. **Tools → Port** → select the COM port your ESP32 is on

### Step 2 — Install Required Libraries

Open **Sketch → Include Library → Manage Libraries** and install:

| Library | Author | Used for |
|---------|--------|----------|
| **ArduinoJson** | Benoit Blanchon | JSON building/parsing |
| **Adafruit ADS1X15** | Adafruit | Flex sensor (ADS1115) |
| **MadgwickAHRS** | Arduino | Sensor fusion |

> `Wire.h`, `WiFi.h`, `HTTPClient.h` are built into the ESP32 board package — no install needed.

---

### Step 3 — Wire the MPU6050 Sensors

Both MPUs share the same 4-wire I2C bus. The **AD0 pin** sets the address:

```
      ESP32                MPU #1 (Torso)       MPU #2 (Neck)
      ─────                ──────────────       ─────────────
      3.3V  ───────────────  VCC          ───── VCC
      GND   ───────────────  GND          ───── GND
      GPIO21 (SDA) ────────  SDA          ───── SDA
      GPIO22 (SCL) ────────  SCL          ───── SCL
      GND   ───────────────  AD0                              ← address 0x68
      3.3V  ──────────────────────────────────  AD0           ← address 0x69
```

> ⚠️ **Use 3.3V — NOT 5V.** MPU6050 is a 3.3V sensor. 5V will damage it.

| Sensor | Location | AD0 pin | I2C Address |
|--------|----------|---------|-------------|
| MPU #1 | T4 (lower back / torso) | → GND   | **0x68** |
| MPU #2 | C7 (neck / upper back)  | → 3.3V  | **0x69** |

#### On a breadboard (2 separate breadboards):

```
  Breadboard 1 (MPU #1 — Torso)    Breadboard 2 (MPU #2 — Neck)
  ┌─────────────────┐               ┌─────────────────┐
  │  MPU6050        │               │  MPU6050        │
  │  VCC → 3.3V     │               │  VCC → 3.3V     │
  │  GND → GND      │               │  GND → GND      │
  │  SDA → GPIO 21  │               │  SDA → GPIO 21  │
  │  SCL → GPIO 22  │               │  SCL → GPIO 22  │
  │  AD0 → GND      │               │  AD0 → 3.3V     │
  └─────────────────┘               └─────────────────┘
```

---

### Step 4 — Test the Sensors (mpu6050_test.ino)

**Upload `Hardware/mpu6050_test.ino`** — no WiFi needed, Wire.h only.

```
Arduino IDE → File → Open → Hardware/mpu6050_test.ino → Upload
```

Open **Serial Monitor at 115200 baud**. You should see:

```
[I2C] Scanning bus...
      0x68 | Found  ← MPU6050 #1 (AD0=GND)  ✅
      0x69 | Found  ← MPU6050 #2 (AD0=3.3V) ✅
      Found 2 device(s)

[T=5s]
  TORSO (0x68)  Pitch= +3.21°  Roll= -1.05°
    Accel: X=+0.056g  Y=-0.018g  Z=+0.998g
    Gyro:  X= +0.31°/s  Y= -0.12°/s  Z= +0.08°/s

  NECK  (0x69)  Pitch= +5.11°  Roll= +2.30°
    Accel: X=+0.089g  Y=+0.040g  Z=+0.995g
    Gyro:  X= -0.22°/s  Y= +0.18°/s  Z= -0.05°/s
```

**What to check:**
- Tilt the sensor forward/backward → **Pitch** should change
- Tilt sideways → **Roll** should change
- Accel Z should be near **+1.0g** when sensor is flat on the table
- Both sensors should show different readings when tilted independently

#### I2C Scan Troubleshooting:

| Scan result | Cause | Fix |
|-------------|-------|-----|
| No devices found | VCC or GND not connected | Check 3.3V and GND wires |
| Only 0x68 found | MPU #2 AD0 not at 3.3V | Connect AD0 of MPU #2 to 3.3V |
| Only 0x69 found | MPU #1 AD0 not at GND | Connect AD0 of MPU #1 to GND |
| Both at 0x68 | Both AD0 pins to GND | One AD0 must go to 3.3V |
| All zeros in readings | SDA/SCL swapped | Swap GPIO 21 and 22 |

---

### Step 5 — Test the Flex Sensor (flex_sensor_test.ino)

> **No extra library needed.** Uses ESP32's built-in 12-bit ADC directly.

The flex sensor is a variable resistor — connect it via a **voltage divider** to **GPIO 34** (ADC1, WiFi-safe).

#### Wiring — Voltage Divider:

```
  3.3V ──── Flex Sensor leg 1
            Flex Sensor leg 2 ──┬──── GPIO 34  (ADC input)
                                │
                             10kΩ resistor
                                │
  GND ────────────────────────────
```

> ⚠️ **Use GPIO 34 only** (or GPIO 35/36/39). These are ADC1 pins and work alongside WiFi.
> Do NOT use GPIO 0, 2, 4, 12–15, 25–27 (ADC2 — conflicts with WiFi).

> ⚠️ **Use 3.3V — NOT 5V.** GPIO 34 max input is 3.3V.

#### Upload and test:

```
Arduino IDE → File → Open → Hardware/flex_sensor_test.ino → Upload
```

Open **Serial Monitor at 115200 baud**. You should see:

```
[T=   2s]  Raw: 3187   Voltage: 2.568V   Bend:   0.0%   [░░░░░░░░░░░░░░]  FLAT
[T=   3s]  Raw: 2100   Voltage: 1.692V   Bend:  60.4%   [████████████░░]  MODERATE BEND
[T=   4s]  Raw: 1380   Voltage: 1.112V   Bend: 100.0%   [██████████████]  FULLY BENT ⚠️
```

**What to check:**
- Bend the sensor → bar fills up, value decreases ✅
- Release flat → bar empties, value increases ✅
- If nothing changes → check voltage divider wiring

#### Calibration (run once):

After bending/flattening a few times, note the `[CAL]` line printed every 10s:
```
Session max (keep flat) : 3187  → use as FLAT_RAW
Session min (bend fully): 1380  → use as BENT_RAW
```
Update in `flex_sensor_test.ino`:
```cpp
int FLAT_RAW = 3187;   // ← your flat value
int BENT_RAW = 1380;   // ← your bent value
```

#### Flex Sensor Troubleshooting:

| Problem | Cause | Fix |
|---------|-------|-----|
| Raw value stuck at 0 | GPIO not connected | Check both legs of flex sensor wired |
| Raw value stuck at 4095 | No pull-down resistor | Add 10kΩ between GPIO 34 and GND |
| Value doesn't change when bending | Sensor wired in wrong direction | Swap flex sensor legs |
| Very noisy / jumping values | ESP32 ADC noise (normal) | Sketch already averages 32 samples |
| Bar always 100% | FLAT/BENT values swapped | Swap FLAT_RAW and BENT_RAW |

---

### Step 6 — Upload WiFi Test (wifi_test.ino)

1. Find your PC's IP on the hotspot (run `ipconfig` → Wireless LAN adapter IPv4)
2. Edit `wifi_test.ino`:
   ```cpp
   const char* WIFI_SSID     = "YourHotspotName";
   const char* WIFI_PASSWORD = "YourPassword";
   const char* BACKEND_IP    = "192.168.X.X";   // your PC's IP
   ```
3. Upload and open Serial Monitor at 115200 baud
4. Should print `✅ Connected!` then `HTTP 200` for each POST

---

### Step 7 — Upload Main Firmware (posture_sensor.ino)

> Do this **after** all component tests pass (MPU + flex + WiFi).

1. Open `Hardware/posture_sensor.ino`
2. Set credentials in `Hardware/config.h`
3. Update calibration values from `flex_sensor_test.ino` results
4. Upload → open Serial Monitor

### ⚠️ How to find your PC's backend IP address

The ESP32 connects to your phone hotspot. Your PC must be on the **same hotspot**.
The ESP32 needs to know your PC's IP on that network.

**Step 1 — Connect your PC to the phone hotspot** ("Backend")

**Step 2 — Find your PC's IP on the hotspot:**

```powershell
# Windows PowerShell or CMD
ipconfig
```

Look for the section called **Wireless LAN adapter Wi-Fi** and find:
```
IPv4 Address. . . . . . . . . . . : 192.168.X.X   ← THIS is your BACKEND_IP
```

> **Example output:**
> ```
> Wireless LAN adapter Wi-Fi:
>    IPv4 Address. . . . . : 192.168.156.23   ← your backend IP
>    Subnet Mask . . . . . : 255.255.255.0
>    Default Gateway . . . : 192.168.156.1
> ```

**Step 3 — Paste it into `wifi_test.ino`:**
```cpp
const char* BACKEND_IP = "192.168.156.23";  // ← your actual IP
```

> **Note:** The IP changes every time you reconnect to the hotspot. Re-run `ipconfig` if the ESP32 stops connecting.

---

## 4. Running the Full System

### Start order:

```
Step 1 → PC joins phone hotspot ("Backend")
Step 2 → cd Backend && python main.py
Step 3 → cd frontend && npm start       (new terminal)
Step 4 → Open http://localhost:3000     (dashboard)
Step 5 → Open http://localhost:8000/docs (Swagger UI for testing)
Step 6 → Upload wifi_test.ino to ESP32  (when ready for hardware)
```

### Testing WITHOUT hardware (Swagger UI):
1. Start backend (`python main.py`)
2. Open `http://localhost:8000/docs`
3. Click **POST /api/sensor-data → Try it out → Execute**
4. Dashboard updates within 200ms

### Verify ESP32 integration:
1. ✅ Serial Monitor shows "Connected!" with an IP address
2. ✅ Serial Monitor shows "HTTP Code : 200"
3. ✅ Backend terminal shows incoming classification logs
4. ✅ Dashboard switches to **LIVE** and shows posture data

---

## Project Structure

```
PoseGuide/
├── frontend/                    # React + TypeScript Dashboard
│   └── src/
│       ├── components/          # UI components (PostureModel, Score, Chart...)
│       ├── hooks/
│       │   └── usePosturePolling.ts  # REST polling hook (200ms)
│       ├── pages/               # Dashboard, Analytics, Settings
│       └── types/posture.ts     # Shared TypeScript interfaces
│
├── Backend/                     # FastAPI Python Server
│   ├── main.py                  # REST + WebSocket server
│   ├── models.py                # Pydantic models
│   ├── posture_classifier.py    # Posture analysis engine
│   └── requirements.txt
│
├── Hardware/
│   ├── wifi_test.ino            # ← START HERE (WiFi + hardcoded data test)
│   ├── posture_sensor.ino       # Full firmware (real sensors, use later)
│   ├── config.h                 # Wi-Fi & sensor config
│   └── README.md
│
├── instructions.md
├── README.md
└── .gitignore
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| ESP32 says "Failed to connect" | Check hotspot name = `Backend`, password = `helloguys`, 2.4GHz only |
| ESP32 shows "HTTP Code: -1" | Backend not running — run `python main.py` in Backend folder |
| ESP32 shows "HTTP Code: -11" | Wrong IP or PC firewall blocking port 8000 — try disabling Windows firewall temporarily |
| ESP32 connects but dashboard stays OFFLINE | PC is not on the same hotspot as ESP32 |
| Frontend stays WAITING | No data posted yet — use Swagger UI or upload wifi_test.ino |
| Backend import errors | Virtual environment not activated — run `.\venv\Scripts\activate` first |
| `npm install` fails | Delete `node_modules` + `package-lock.json`, then `npm install --force` |
| IP address changed | Run `ipconfig` again, update `BACKEND_IP` in the .ino file and re-upload |
