# PoseGuide – Setup & Run Instructions

> Complete step-by-step commands to set up and run all three subsystems.

---

## Prerequisites

| Tool | Version | Check Command |
|------|---------|---------------|
| **Node.js** | v18+ | `node --version` |
| **npm** | v9+ | `npm --version` |
| **Python** | 3.10+ | `python --version` |
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

## 3. Hardware Setup (ESP32)

### Install Required Libraries in Arduino IDE:
1. Open **Arduino IDE → Library Manager** (Ctrl+Shift+I)
2. Search and install:
   - **ArduinoWebsockets** by Gil Maimon
   - **ArduinoJson** by Benoit Blanchon (v7+)
   - **Adafruit ADS1X15** by Adafruit
   - **MadgwickAHRS** by Arduino

### Install ESP32 Board Support:
1. Open **Arduino IDE → File → Preferences**
2. Add this URL to "Additional Board Manager URLs":
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Open **Tools → Board → Board Manager** → Search "ESP32" → Install
4. Select board: **ESP32 Dev Module**

### Configure and Upload:
1. Open `Hardware/posture_sensor.ino` in Arduino IDE
2. Edit `Hardware/config.h`:
   ```cpp
   #define WIFI_SSID       "YourWiFiName"
   #define WIFI_PASSWORD   "YourWiFiPassword"
   #define SERVER_HOST     "192.168.x.x"  // Your PC's local IP address
   ```
3. Connect ESP32 via USB
4. Select the correct **COM port** under Tools
5. Click **Upload**
6. Open **Serial Monitor** (115200 baud) to see connection status

### Find your PC's local IP:
```bash
# Windows
ipconfig

# macOS/Linux
ifconfig
```
Look for the IPv4 address on your Wi-Fi adapter (e.g., `192.168.1.100`).

---

## 4. Running the Full System

### Start order:

```
Step 1: Backend    →  cd Backend && python main.py
Step 2: Frontend   →  cd frontend && npm start
Step 3: Hardware   →  Power on ESP32 (already uploaded)
```

### Verify integration:
1. ✅ Backend terminal shows: `ESP32 connected`
2. ✅ Backend terminal shows: `Dashboard client connected`
3. ✅ Frontend dashboard switches from **Demo Mode** to **Live Mode**
4. ✅ 3D model moves in sync with your body movements
5. ✅ Posture score and alerts update in real-time

---

## Project Structure

```
PoseGuide/
├── frontend/                    # React + TypeScript Dashboard
│   ├── public/
│   │   └── index.html           # SEO-optimized HTML shell
│   ├── src/
│   │   ├── components/
│   │   │   ├── AlertBanner/     # Posture warning notifications
│   │   │   ├── AngleChart/      # Real-time time-series chart
│   │   │   ├── Layout/          # App shell with sidebar
│   │   │   ├── PostureModel/    # 3D human skeleton (Three.js)
│   │   │   ├── PostureScore/    # Circular score gauge
│   │   │   ├── Sidebar/         # Navigation sidebar
│   │   │   └── SensorStatus/    # Sensor connection panel
│   │   ├── hooks/
│   │   │   └── usePostureSocket.ts  # WebSocket hook
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx    # Main monitoring page
│   │   │   ├── Analytics.tsx    # Session statistics
│   │   │   └── Settings.tsx     # Configuration page
│   │   ├── types/
│   │   │   └── posture.ts       # Shared TypeScript interfaces
│   │   ├── utils/
│   │   │   └── postureClassifier.ts  # Score colors & labels
│   │   ├── App.tsx              # Root with routing
│   │   ├── App.css
│   │   └── index.css            # Design system
│   ├── package.json
│   └── tsconfig.json
│
├── Backend/                     # FastAPI Python Server
│   ├── main.py                  # WebSocket server
│   ├── models.py                # Pydantic data models
│   ├── posture_classifier.py    # Posture analysis engine
│   ├── config.py                # Thresholds & settings
│   ├── requirements.txt
│   └── venv/
│
├── Hardware/                    # ESP32 Arduino Firmware
│   ├── posture_sensor.ino       # Main firmware sketch
│   ├── config.h                 # Wi-Fi & sensor config
│   └── README.md                # Wiring & setup guide
│
├── instructions.md              # ← You are here
├── README.md                    # Project overview
└── .gitignore
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Frontend shows "Demo Mode" | Ensure backend is running and ESP32 is connected |
| WebSocket connection fails | Check that backend is on port 8000 and CORS allows localhost:3000 |
| ESP32 won't connect to Wi-Fi | Verify SSID/password in `config.h`, check 2.4GHz network |
| Sensor readings are erratic | Check I2C wiring, verify MPU addresses (0x68, 0x69) |
| Backend import errors | Ensure virtual environment is activated before running |
| `npm install` fails | Try deleting `node_modules` and `package-lock.json`, then retry |
