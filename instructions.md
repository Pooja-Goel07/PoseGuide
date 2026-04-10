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
