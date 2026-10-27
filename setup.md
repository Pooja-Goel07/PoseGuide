# PoseGuide — Setup & Run Guide

This guide gets the whole system running locally: the FastAPI **backend**, the
React **dashboard**, and a **mock hardware** source (either the ESP32 firmware or
a Python stand-in). Everything runs on `localhost` — no cloud, no MQTT.

> **Architecture at a glance**
>
> ```
> mock hardware ──HTTP POST JSON──▶  FastAPI backend  ──poll──▶  React dashboard
>  (ESP32 or                          · validates                (port 3000)
>   Python sender)                    · classifies (baseline + personalized)
>                                     · persists to SQLite
>  (port 8000)
> ```

---

## 1. Prerequisites

| Tool | Version used | Notes |
|------|--------------|-------|
| Python | 3.11+ (tested 3.13) | backend + ML + tests |
| Node.js | 18+ (tested 22) | dashboard build/dev |
| npm | 9+ (tested 10) | ships with Node |
| Arduino IDE **or** PlatformIO | latest | **only** if flashing the ESP32 (optional) |

You do **not** need any hardware to run and demo the full system — the Python
mock sender replaces the ESP32.

---

## 2. Backend (FastAPI)

```bash
cd Backend

# (recommended) create + activate a virtual environment
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt

# run the server (http://localhost:8000)
python main.py
```

Verify it's up:
- Swagger UI → <http://localhost:8000/docs>
- Health → <http://localhost:8000/health>
- Latest → <http://localhost:8000/api/latest>

The SQLite file `Backend/poseguide.db` is created automatically on first run.

### Key endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/sensor-data` | ingest a reading → validate → classify → store |
| GET  | `/api/latest` | most recent classified reading (both classifiers) |
| GET  | `/api/status` | sensor online/offline, fault counters, last error |
| GET  | `/api/history?limit=N` | recent readings for the charts |
| POST | `/api/calibrate/start` | begin collecting personalization samples |
| POST | `/api/calibrate/stop` | fit μ, Σ, τ and activate the personalized model |
| GET  | `/api/calibrate/status` | live sample count / τ |
| POST | `/api/calibrate/reset` | clear the personalized model |

---

## 3. Frontend (React + TypeScript dashboard)

```bash
cd frontend
npm install
npm run dev        # opens http://localhost:3000
```

The dashboard polls the backend at `http://localhost:8000` by default. To point
it elsewhere, set `VITE_API_BASE` before `npm run dev`, e.g.:

```bash
# PowerShell
$env:VITE_API_BASE="http://192.168.1.50:8000"; npm run dev
```

What you'll see: a 3-D posture avatar, live angle gauges, a **sensor
online/offline** pill with fault counters, **baseline vs. personalized** verdict
cards side by side, a calibration control, and a history chart.

---

## 4. Mock hardware (choose ONE)

### Option A — Python sender (no board needed, recommended for demo)

With the backend running:

```bash
cd Backend
python -m tools.mock_sender                     # stream realistic posture data
python -m tools.mock_sender --faults            # also inject the two faults
python -m tools.mock_sender --state normal --count 60   # feed a clean baseline
```

Typical calibration demo:
1. In the dashboard, click **Start Calibration**.
2. Run `python -m tools.mock_sender --state normal --count 60`.
3. Click **Stop & Fit Model** → the personalized model activates (shows τ).
4. Run `python -m tools.mock_sender` again and watch the two cards diverge on
   sub-threshold deviations.

### Option B — ESP32 firmware (real board, optional)

Open `Hardware/posture_mock_http/posture_mock_http.ino` in the Arduino IDE.

1. Install libraries: **ArduinoJson** (v7+). `WiFi` and `HTTPClient` ship with
   the ESP32 board package.
2. Edit the config block at the top:
   - `WIFI_SSID`, `WIFI_PASSWORD`
   - `SERVER_HOST` = your PC's LAN IP (find it: `ipconfig` on Windows →
     "IPv4 Address"; `hostname -I` on Linux/mac). The PC running the backend and
     the ESP32 must be on the same network.
3. Make sure the backend listens on all interfaces (it already binds `0.0.0.0`).
4. Flash and open the Serial Monitor at 115200 baud.

The sensor reads are **stubbed** with generated values (no physical MPU-6050 is
required). Fault injection is togglable via the `#define`s near the top
(`ENABLE_INVALID_FAULT`, `ENABLE_DROPOUT_FAULT`, and their duty cycles).

> Live on-board flashing was **not** performed while building this iteration; the
> firmware is written to be correct and buildable, and to swap to real sensors by
> replacing only `sampleReading()`.

---

## 5. Run the test suite

```bash
cd Backend
pip install -r requirements.txt   # includes pytest + httpx
python -m pytest                  # 46 tests, ~2 s
```

Tests use a throwaway temp database, so they never touch `poseguide.db`.

## 6. (Optional) Regenerate the dataset / benchmark

```bash
cd Backend
python -m data.generate_dataset            # -> data/poseguide_dataset.csv
python -m tools.benchmark                  # prints the numbers used in results.md
```

---

## 7. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| Dashboard shows "Backend unreachable" | Backend not running, or CORS. It must be on port 8000; the dev server must be on port 3000 (both are in the allow-list in `Backend/config.py`). |
| CORS error in browser console | Add your dashboard origin to `ALLOWED_ORIGINS` in `Backend/config.py`. |
| `Address already in use` on port 8000/3000 | Another process (or a previous run) holds the port. Stop it, or change the port (`main.py` `PORT`, `vite.config.ts` `server.port`). |
| `poseguide.db ... Device or resource busy` | A previous backend is still running — stop it before deleting/reinitialising the DB. |
| ESP32 can't reach backend | Wrong `SERVER_HOST` IP, different Wi-Fi network, or a firewall blocking inbound 8000. Confirm the PC's IP and that both devices share the LAN. |
| Sensor shows "Offline" in dashboard | No valid reading in the last 8 s (`SENSOR_TIMEOUT_SECONDS`). Start the mock sender / firmware. |
| `No module named pytest` | `pip install -r requirements.txt` inside the active venv. |
