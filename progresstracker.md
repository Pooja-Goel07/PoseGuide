# PoseGuide — Progress Tracker

**Last updated:** 2026-09-04

> ## ▶ Resume here
> The Assessment-6 prototype is **feature-complete and verified end-to-end**:
> 3-feature model, backend-hosted personalization (Mahalanobis), dual-classifier
> API, React dashboard, HTTP-POST mock firmware, 46 passing tests, and real
> benchmark numbers. **Next session's first job:** if you want live-hardware
> numbers, flash `Hardware/posture_mock_http/` and point it at your PC's IP;
> otherwise the Python mock sender already drives the full system. Then paste the
> separately-produced Wokwi results into the placeholder at the bottom of
> `results.md`.

---

## Scope notes (decided, intentional)
- **Personalization runs in the backend, not on the ESP32** — deliberate,
  documented scope reduction from the paper's on-device design so the model is
  buildable/testable in the available time. Listed as a Future Enhancement.
- **No flex sensor this iteration** → feature vector is 3-D
  `[torso_pitch, torso_roll, neck_relative_pitch]`. All flex references removed
  from the new model path.
- **Transport is plain HTTP POST** (JSON), no MQTT/WebSocket in the new path.
- The Assessment-5 Wokwi project is untouched and out of scope here.

---

## Hardware  ✅
- ✅ New self-contained ESP32 sketch `Hardware/posture_mock_http/posture_mock_http.ino`
  — HTTP POST transport, sensor reads **stubbed** with a plausible posture state
  machine mirroring the backend generator.
- ✅ Fault injection built in and **togglable** via `#define`:
  Fault A (invalid: out-of-range + NaN, `INVALID_EVERY_N`),
  Fault B (dropout 10–20 s, `DROPOUT_EVERY_N`).
- ✅ Wi-Fi SSID/password/server-IP as clearly-marked placeholders at the top.
- ✅ Python stand-in `Backend/tools/mock_sender.py` for driving the system with
  no board flashed (same generator, same faults).
- 🚫 Live on-board flashing/testing — **out of scope this session** (no physical
  sensors wired). Code is written to be correct/buildable.

## Backend (FastAPI)  ✅
- ✅ 3-feature Pydantic models (`models.py`), flex removed.
- ✅ `POST /api/sensor-data` — validate → dual-classify → persist → return.
- ✅ Distinct validation faults: `malformed_payload`, `missing_field`,
  `non_finite` (NaN/inf), `out_of_range` (|angle|>180) → HTTP 400, **without**
  corrupting last-good state.
- ✅ `GET /api/latest`, `GET /api/status` (online/offline + counts + last error),
  `GET /api/history`, analytics endpoints.
- ✅ `POST /api/calibrate/start|stop|status|reset`.
- ✅ Sensor online/offline via staleness timeout (`SENSOR_TIMEOUT_SECONDS = 8 s`).
- ✅ Calibration persisted in SQLite (`calibration` table), reloaded on startup.
- ✅ Migrated deprecated `on_event` → `lifespan`.

## ML model  ✅
- ✅ Isolated `Backend/ml/` package (no FastAPI deps → directly unit-testable):
  `constants` (single source of truth), `features`, `baseline`, `personalized`.
- ✅ Baseline fixed-threshold classifier (3-feature) with critical override.
- ✅ Proposed personalized model: calibration → mean μ + covariance Σ (numpy),
  Mahalanobis distance, τ = 95th percentile, `"personalized_deviation"` flag.
- ✅ Safety override checked **identically** to baseline; can never be suppressed.
- ✅ Clean baseline fallback before calibration / too-few / singular Σ, honestly
  reporting `model: "baseline"`.
- ✅ Shared synthetic generator + `data/generate_dataset.py` →
  `data/poseguide_dataset.csv` (2000 rows).

## Frontend (React + TS + Three.js + Recharts)  ✅
- ✅ Scaffolded fresh (the repo's `frontend/` was empty) with Vite on **port 3000**.
- ✅ 3-D posture avatar (Three.js) tilting to live angles.
- ✅ Live angle gauges; sensor online/offline + fault counters in the status bar.
- ✅ **Side-by-side** baseline vs. personalized cards (the comparison at a glance).
- ✅ Calibration control with live progress + resulting τ.
- ✅ Recharts history (score + Mahalanobis + τ line).
- ✅ `npm run build` passes (tsc + vite).

## Testing  ✅
- ✅ 46 pytest cases across normal / boundary / abnormal / personalized / faults.
- ✅ **All 46 pass** (`python -m pytest`, ~1.6 s).
- ✅ Real benchmark (`tools/benchmark.py`) → numbers in `results.md`.
- ✅ Live end-to-end run (uvicorn + mock sender) verified, incl. both faults.

## Docs  ✅
- ✅ `progresstracker.md` (this file), `setup.md`, `results.md`.

---

## Known issues / open questions
- Frontend bundle is ~1 MB (three.js + recharts). Fine for a local dashboard;
  could code-split later. Not a functional issue.
- `results.md` energy/on-device figures are **labelled estimates** (no physical
  board measured this session).
- Wokwi-derived results are produced separately — placeholder left in `results.md`.
- If you re-run tests and see a busy `poseguide.db`, a previous uvicorn is still
  running — stop it first (tests use a temp DB and are unaffected).
