# CLAUDE.md — PoseGuide: Assessment-6 Prototype Build

> This file is the handoff brief for Claude Code. Read it fully before writing any code.
> If anything here conflicts with what you find in the existing repo, trust the repo's
> actual state, note the discrepancy in `progresstracker.md`, and proceed with the more
> current/correct assumption.

---

## 0. Context — what already exists, what this session adds

There is an **existing basic version** of this project already in this repo: ESP32 firmware
reading 2× MPU-6050 + a flex sensor, a Python/FastAPI backend, a SQLite database, and a
React + TypeScript + Three.js dashboard doing **fixed-threshold** posture classification
(no personalization, no ML). **Open and inspect the existing repo structure first** —
don't assume file paths; find out what's actually there and extend it.

This session's job is to evolve that basic version into the prototype needed for
**Assessment-6 (IoT Integration, Testing & Performance Evaluation)** — which means the
system needs to actually run end-to-end and be testable, not just exist as design docs.

**Do not touch or worry about the Wokwi simulation.** A separate Assessment-5 Wokwi
project already exists (2× MPU-6050 + flex sensor + buzzer + LED, on-device
fixed-threshold classification only, no Wi-Fi). That stays exactly as-is. Any
Wokwi-derived results for Assessment-6 will be produced separately in a different
conversation, not by you. Your scope is the backend/frontend/ML/mock-hardware system
described below.

---

## 1. Hard constraints — decided, do not relitigate these

These were explicit decisions made before this build started. Don't "improve" them
without asking first.

1. **The unsupervised personalization model runs in the backend, not on the ESP32.**
   The original research paper's design was fully on-device for privacy; this prototype
   iteration deliberately simplifies that to make the model actually buildable and
   testable in the time available. This is a *documented, intentional scope reduction*,
   not an oversight — say so explicitly in any docs you write, and list "move the
   personalized model back on-device (ESP32/edge)" as one of the Assessment-6 Future
   Enhancement items (Section 8 of the assessment explicitly invites this).
2. **No flex sensor this iteration.** Only 2× MPU-6050 (torso @ T4, neck @ C7). This
   changes the feature vector from 4D to **3D**: `[torso_pitch, torso_roll,
   neck_relative_pitch]`. Update every part of the codebase and every doc that
   referenced the 4-feature version accordingly — don't leave stale references to
   `flex_value` in the new model path.
3. **Hardware layer = real Arduino/ESP32 C++ firmware**, not a Python mock script. It
   should look and behave like real firmware (so it could later be pointed at real
   MPU-6050s with minimal changes) but **stub the sensor reads with generated plausible
   values** instead of calling `Wire`/`Adafruit_MPU6050`, since there's no physical
   sensor wired up. It still sends data over Wi-Fi via **HTTP POST** — same transport as
   the original design, no MQTT.
4. **Communication is plain HTTP POST**, JSON payloads, matching the original design's
   pattern. No MQTT broker, no cloud IoT platform for this iteration.
5. **Everything runs locally** (localhost backend + localhost/dev-server frontend +
   firmware pointed at that local IP, or a local IP the user configures). No cloud
   deployment assumed.

---

## 2. The four sections

Structure new work into these four clearly separated areas. If the existing repo already
has a different structure, adapt to it but keep this separation conceptually clear
(e.g., the ML logic should be its own importable module, not inlined into API route
handlers).

### 2.1 Hardware code (`hardware/` or wherever the existing firmware lives)

- Arduino/ESP32 C++ sketch. Generates a plausible 3-feature reading every ~300–500 ms
  and sends it via `HTTPClient` POST to the backend, matching the JSON schema in
  Section 4 below.
- **"Plausible" means realistic simulated posture behavior, not uniform random noise.**
  Model it as: mostly hovering near a "normal sitting" baseline (small variation), with
  periodic simulated excursions into each condition type (slouch, forward head, lateral
  lean, critical) so the live dashboard and test results actually have something
  meaningful to show — reuse the same generation logic/parameters as the existing
  `poseguide_dataset.csv` synthetic dataset if that file is present in the repo, for
  consistency.
- **Deliberately build in material for the fault-handling requirement** (Assessment-6
  needs ≥2 demonstrated fault conditions):
  - Occasionally emit an **out-of-range/invalid reading** (e.g., a NaN, an
    out-of-physical-range angle, or a malformed payload) so the backend's validation
    logic has something real to catch and reject.
  - Occasionally **stop sending for 10–20 seconds** (simulated network/sensor dropout)
    so the backend's staleness/timeout detection has something real to trigger on.
  - Make both of these togglable/configurable (e.g., a `#define` or a duty-cycle
    constant), not constant nuisances — they need to be demonstrable on request, not
    randomly firing during every other test.
- Wi-Fi SSID/password as placeholders/config at the top of the file, clearly marked for
  the user to fill in before any real flashing.
- You are not expected to flash or run this firmware — just write correct, clean,
  buildable Arduino code. Note in `progresstracker.md` that live firmware testing is
  out of scope for this session.

### 2.2 Backend (FastAPI, extending the existing one)

- New endpoints needed (adapt names to whatever convention the existing backend already
  uses):
  - `POST /api/sensor-data` — receives a hardware reading, validates it, runs it through
    both classifiers (Section 2.3), persists the classified result, returns the result.
  - `POST /api/calibrate/start`, `POST /api/calibrate/stop` — controls the
    personalization calibration window (Section 2.3).
  - `GET /api/latest` — most recent classified reading (for dashboard polling, matches
    original design pattern).
  - `GET /api/history` / analytics endpoints — for the dashboard's historical
    graphs/alerts feed.
  - Whatever is needed to expose fault/status info to the frontend (e.g., "sensor
    offline" state, last-seen timestamp).
- **Validation and fault handling belong here.** Reject/flag physically impossible
  values (e.g., |angle| > 180°, NaN, missing fields) distinctly from posture-anomaly
  classification — these are two different kinds of "bad": one is a broken sensor
  reading, the other is a real posture deviation. Track "last reading received at" and
  expose a derived "sensor online/offline" status based on a timeout.
- Keep the ML logic (Section 2.3) in its own importable module — the API layer should
  call into it, not contain it.

### 2.3 ML model (new — this is the actual novel contribution, keep it isolated and testable)

Implement **both** classifiers so the assessment's "baseline vs proposed" comparison
(Assessment-6 Section 3) has two real things to compare, not one real and one
hypothetical:

**Baseline (already exists in some form in the current Wokwi/original code — port/reuse the same logic and constants):**

```
Δθx = max(0, |θx| − 10°)
Score = max(0, 100 − 1.5·Δθ_pitch − 1.2·Δθ_roll − 1.8·Δθ_neck)

Good:             all angles within threshold
Slouching:        |torso_pitch| > 25°
Forward Head:     neck_relative_pitch > 20°
Lateral Lean:     |torso_roll| > 15°
Multiple Issues:  ≥2 of the above simultaneously
Critical:         |torso_pitch| > 40° OR neck_relative_pitch > 35°   (overrides all else)
```

**Proposed (new — implement this for real, it's the point of the whole prototype):**

1. Calibration: while a calibration session is active (`/api/calibrate/start` …
   `/api/calibrate/stop`), collect incoming feature vectors
   `x = [torso_pitch, torso_roll, neck_relative_pitch]`. On stop, compute mean vector
   `μ` and covariance matrix `Σ` from the collected samples (use `numpy`). Persist
   `μ`, `Σ` (SQLite or a simple serialized file — whatever fits the existing DB
   pattern) so calibration survives a restart.
2. Scoring: for each new reading, compute the Mahalanobis distance
   `D_M(x) = sqrt((x − μ)ᵀ Σ⁻¹ (x − μ))`.
3. Personalized threshold `τ_personal` = the 95th percentile of the `D_M` values
   computed over the calibration set itself.
4. Flag `"Personalized Deviation"` if `D_M > τ_personal`.
5. **Safety override is non-negotiable**: regardless of `D_M`, if
   `|torso_pitch| > 40°` or `neck_relative_pitch > 35°`, the result is `"Critical"`.
   This must be checked identically to the baseline's critical check — the personalized
   layer can never suppress it.
6. Before calibration has been run (or with too few samples — guard against a
   singular/near-singular `Σ`), fall back cleanly to baseline-only behavior and say so
   in the API response (e.g., `"model": "baseline"` vs `"model": "personalized"` in the
   response payload) — don't crash, and don't silently pretend to be personalized when
   you're not.
- Write this as testable, pure functions (numpy in, dict out) — no FastAPI/HTTP
  dependency inside the ML module itself — so it's directly unit-testable (Section 3).

### 2.4 Frontend (React + TypeScript + Three.js + Recharts, extending the existing dashboard)

Assessment-6 explicitly requires all of the following on the dashboard — make sure each
is actually visible, not just technically present in the data:

- Real-time sensor values (live angles, updating).
- Device/actuator status — including the new **sensor online/offline** status derived
  from backend staleness detection (Section 2.2).
- Alerts — surface both classifiers' current condition, ideally **side by side**
  (baseline condition vs. personalized condition) so the comparison the assessment
  wants is visible at a glance, not just computable from raw logs.
- Historical graphs — score/condition over time (Recharts, matches existing pattern).
- A calibration control: start/stop calibration, and some visible indication of
  calibration progress/status (e.g., "collecting… 42 samples" → "calibrated, τ = 3.2").

---

## 3. Testing (feeds directly into `results.md` — Assessment-6 needs this)

Write real automated tests (pytest for backend/ML), covering **at minimum** these
categories (Assessment-6 requires ≥5 test cases spanning normal/boundary/abnormal):

- Normal: a clearly-good-posture reading classifies as `"Good"` on both classifiers.
- Boundary: readings placed exactly at/just past each threshold (25°, 20°, 15°, 40°,
  35°) — verify the classification flips exactly where it should.
- Abnormal/invalid: NaN, out-of-physical-range angle, missing field — verify the
  backend rejects/flags rather than crashing or silently misclassifying.
- Personalized-model-specific: too-few-calibration-samples fallback behaves correctly;
  a reading far outside a tight calibrated baseline correctly triggers
  `"Personalized Deviation"` even when under the fixed thresholds (this is the actual
  demonstration that personalization adds value beyond the baseline).
- Fault handling: simulated sensor dropout is correctly detected as "offline" after the
  timeout window; a burst of invalid payloads doesn't corrupt state for subsequent valid
  ones.

Run these for real. Don't hand-write a results table from imagination when a genuine
`pytest` run can produce the real pass/fail and timing numbers.

---

## 4. Data contract (hardware → backend)

```json
{
  "torso": { "pitch": -2.3, "roll": 1.1 },
  "neck":  { "pitch": 5.6 },
  "timestamp": 1234567
}
```

`neck_relative_pitch` is derived server-side as `|neck.pitch − torso.pitch|`, matching
the existing design — don't compute it on the firmware side.

---

## 5. Three docs to create and actively maintain

Create these at the repo root. Update them as you work — don't write them once at the
end. Each has a specific job:

### `progresstracker.md`
Living status doc so work can pause and resume across sessions, possibly weeks apart.
Structure:
- Last-updated date at the top.
- One section per area (Hardware / Backend / ML Model / Frontend / Testing / Docs),
  each a checklist with a status marker (✅ done / 🔄 in progress / ⬜ not started /
  🚫 blocked) per item.
- A "Known issues / open questions" section.
- A "Resume here" pointer at the very top — one or two sentences on exactly what the
  next session should do first.

### `setup.md`
Plain, explanatory, assumes the reader is not already deep in this codebase. Cover:
prerequisites (Python/Node versions, Arduino IDE or PlatformIO), step-by-step backend
setup and run, frontend setup and run, how to run the mock hardware firmware (or how to
point it at a local test server if it's not being flashed), how to run the test suite,
how to open the dashboard, and a short troubleshooting section for the most likely
failure points (port conflicts, CORS, missing env vars).

### `results.md`
This is what gets handed back for the Assessment-6 write-up, so structure it around the
assessment's own sections:
- **Test Cases** — table: ID, description, type (normal/boundary/abnormal), input,
  expected output, actual output, pass/fail. Populate from real `pytest` runs.
- **Performance Comparison** — baseline vs. proposed, covering: accuracy, response
  time, detection rate, false-positive rate, resource utilization, prediction accuracy.
  Measure what's genuinely measurable in this environment (response time, accuracy
  against the test set, resource usage of the backend process). For anything not
  measurable without real hardware (e.g., true device energy consumption), give a
  clearly-labeled **estimate** grounded in realistic figures (e.g., typical ESP32 Wi-Fi
  active-transmit current draw from its datasheet) — label it as an estimate, not a
  measurement, and keep it plausible rather than suspiciously precise.
- **Fault-Handling** — the ≥2 fault conditions implemented, how each was induced, how
  the system detected it, how it responded, with a log/output snippet as evidence.
- **Expected vs. Actual** — comparison table plus a short explanation of any deviations.
- Leave a clearly marked placeholder section at the bottom for **Wokwi-derived results**
  — that part gets filled in separately, not by you.

---

## 6. What "done" looks like for this session

- Existing repo extended (not replaced) with the 3-feature model, backend-hosted
  personalization, and updated firmware.
- Both classifiers genuinely running and comparable via the dashboard and via test
  output.
- At least 2 fault conditions genuinely demonstrable, not just described.
- `progresstracker.md`, `setup.md`, `results.md` all created and reflect real, current
  state — not aspirational descriptions of what should eventually exist.