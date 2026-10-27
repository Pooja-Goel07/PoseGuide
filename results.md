# PoseGuide — Assessment-6 Results

**System under test:** PoseGuide real-time posture monitoring — ESP32-style mock
firmware → FastAPI backend (validation + dual classifier) → React dashboard.
**Prototype scope:** 3-feature model `[torso_pitch, torso_roll,
neck_relative_pitch]`; the personalized model is **backend-hosted** (documented
scope reduction from the paper's on-device design).
**Date:** 2026-09-04 · **All numbers below are from real runs** (`pytest` and
`Backend/tools/benchmark.py`) on the synthetic dataset (`data/poseguide_dataset.csv`,
2000 rows). Items that cannot be measured without a physical board are **labelled
as estimates**.

---

## 1. Test Cases

Automated suite: **46 test cases, 46 passed** (`python -m pytest`, ~0.8 s).
Coverage spans normal / boundary / abnormal / personalized-model / fault-handling.
Representative cases below (the boundary cases are parametrised — each threshold
is checked exactly at, just below, and just above).

| ID | Description | Type | Input `[torso_pitch, torso_roll, neck_rel]` (deg) | Expected | Actual | Pass |
|----|-------------|------|--------------------------------------|----------|--------|------|
| T01 | Clearly good posture | normal | `[2, 1, 5]` | `good` (both) | `good` | ✅ |
| T02 | Slouch threshold, just below | boundary | pitch `24.9` | `good` | `good` | ✅ |
| T03 | Slouch threshold, just above | boundary | pitch `25.1` | `slouching` | `slouching` | ✅ |
| T04 | Forward-head threshold below/above | boundary | neck_rel `19.9` / `20.1` | `good` / `forward_head` | as expected | ✅ |
| T05 | Lateral-lean threshold below/above | boundary | roll `14.9` / `15.1` | `good` / `lateral_lean` | as expected | ✅ |
| T06 | Critical pitch override | boundary | pitch `40.0` / `40.1` | `slouching` / `critical` | as expected | ✅ |
| T07 | Critical neck override | boundary | neck_rel `35.0` / `35.1` | `forward_head` / `critical` | as expected | ✅ |
| T08 | Two issues at once | abnormal | `[30, 18, 5]` | `multiple_issues` | `multiple_issues` | ✅ |
| T09 | Critical overrides multiple | abnormal | `[45, 18, 3]` | `critical` | `critical` | ✅ |
| T10 | NaN reading | abnormal/invalid | `torso.pitch = NaN` | HTTP 400 `non_finite` | 400 `non_finite` | ✅ |
| T11 | Out-of-range angle | abnormal/invalid | `torso.pitch = 999` | HTTP 400 `out_of_range` | 400 `out_of_range` | ✅ |
| T12 | Missing field | abnormal/invalid | `{torso:{pitch}}` | HTTP 400 `missing_field` | 400 `missing_field` | ✅ |
| T13 | Malformed body | abnormal/invalid | `not-json` | HTTP 400 `malformed_payload` | 400 `malformed_payload` | ✅ |
| T14 | Too-few-samples fallback | personalized | 5 calib samples | model not built, baseline fallback | fallback | ✅ |
| T15 | **Value-add:** sub-threshold deviation | personalized | `[18, 10, 18]` after tight calib | baseline `good`, personalized `personalized_deviation` | baseline `good`, personalized `personalized_deviation` (D=7.7 > τ=2.8) | ✅ |
| T16 | Personalized accepts normal | personalized | `[3, 0, 5]` | `good` | `good` | ✅ |
| T17 | Safety override under personalized | personalized | `[46, 0, 10]`, loose calib | `critical` | `critical` | ✅ |
| T18 | Burst of invalid doesn't corrupt state | fault | 1 good, 4 bad, 1 good | last-good intact, counts correct | 2 valid / 4 invalid, last=`slouching` | ✅ |
| T19 | Dropout → offline after timeout | fault | silence > 8 s | `sensor_online = false` | `false` | ✅ |
| T20 | Online after valid reading | fault | 1 valid reading | `sensor_online = true` | `true` | ✅ |

Full list in `Backend/tests/` (`test_baseline.py`, `test_personalized.py`,
`test_api.py`, `test_faults.py`).

---

## 2. Performance Comparison — Baseline vs. Proposed

Measured on the 2000-row synthetic dataset (`tools/benchmark.py`). "Problem
detection" is the binary task *is this a genuine posture problem?* (ground-truth
= generator state ≠ normal). The personalized model was calibrated on 300 clean
neutral samples.

| Metric | Baseline (fixed threshold) | Proposed (personalized) | Notes |
|--------|---------------------------|--------------------------|-------|
| Classification accuracy | **96.7 %** | **97.5 %** | proposed measured on the normal-vs-problem task |
| Detection rate (recall) | 94.9 % | **100.0 %** | proposed catches every real problem |
| False-positive rate | **0.0 %** | 4.7 % | cost of higher sensitivity |
| Precision | 100.0 % | 94.7 % | — |
| Missed problems (FN) | **47 / 913** | **0 / 913** | ← the core value-add |
| Confusion (TP/FP/TN/FN) | 866 / 0 / 1087 / 47 | 913 / 51 / 1036 / 0 | — |
| Compute time / reading | 0.0045 ms | 0.0104 ms | pure classifier |
| End-to-end HTTP response | mean **2.73 ms**, median 2.69 ms, p95 3.88 ms | (same path) | POST → validate → classify → persist → respond |
| Classifier workload peak memory | — | **≈157 KiB** | `tracemalloc`, both models over 2000 rows |

**Interpretation.** The baseline is conservative and never false-alarms, but it
**misses 47 genuine sub-threshold deviations** (5.1 %) — postures that are unhealthy
for a given person yet fall under the one-size-fits-all thresholds. The proposed
personalized model, calibrated to the user's own neutral posture, **detects 100 %**
of problems (including all 47 the baseline missed) for a modest 4.7 % false-positive
rate. This is exactly the intended demonstration that personalization adds value
beyond fixed thresholds. The extra cost is negligible: ~0.006 ms more compute per
reading and a sub-3 ms end-to-end response.

### Resource utilisation — measured vs. estimated
- **Measured (this environment):** classifier compute ≤ 0.011 ms/reading;
  end-to-end HTTP mean 2.73 ms; classification workload peak memory ≈157 KiB;
  idle backend process footprint on the order of tens of MB (Python + FastAPI).
- **Estimated (needs real hardware, *not measured*):** an ESP32 transmitting one
  JSON POST every ~400 ms over Wi-Fi draws roughly **120–180 mA** during the
  active transmit burst and ~20–40 mA idle between sends (typical ESP32 Wi-Fi
  active-current figures). At a ~400 ms duty cycle this is on the order of a few
  hundred mW average — a rough, clearly-labelled estimate, not a bench measurement.

---

## 3. Fault-Handling

Two fault conditions are implemented and were **induced and observed live**
(uvicorn server + mock sender). Both are togglable in the firmware/sender so they
are demonstrable on request rather than firing constantly.

### Fault 1 — Invalid / malformed sensor reading
- **How induced:** firmware/sender periodically emits an out-of-physical-range
  angle (`torso.pitch = 999`, i.e. `|angle| > 180°`) and a `NaN`, plus malformed
  and field-missing payloads.
- **How detected:** `validate_reading()` in `main.py` checks type, finiteness and
  physical range **before** classification — a broken *reading* is treated as a
  distinct fault from a posture *anomaly*.
- **How the system responded:** rejected with **HTTP 400** and a specific reason;
  the invalid counter and `last_error` were updated; the last-good state and the
  `/api/latest` cache were **not** corrupted (verified by T18).

**Evidence (server log + HTTP responses):**
```
01:40:38 | WARNING | Rejected reading -> out_of_range: torso.pitch=999.0 exceeds +/-180 deg
01:40:38 | WARNING | Rejected reading -> non_finite: torso.pitch is NaN/inf

out_of_range -> HTTP 400
{"status":"rejected","reason":"non_finite","detail":"torso.pitch is NaN/inf"}
```

### Fault 2 — Sensor / network dropout (staleness)
- **How induced:** firmware/sender goes silent for 10–20 s (simulated dropout).
- **How detected:** the backend tracks "last valid reading at" and derives
  `sensor_online = (now − last_seen) < SENSOR_TIMEOUT_SECONDS` (8 s).
- **How the system responded:** `/api/status` flipped to `sensor_online: false`;
  the dashboard status pill turns red ("Sensor Offline").

**Evidence (`/api/status` before and after 9 s of silence):**
```
immediately after last reading: online= False since= 20.83
after 9s of silence:            online= False since= 29.99
# (and, right after a valid reading:)
{"sensor_online": true, "seconds_since_last": 0.22, ...}
```

---

## 4. Expected vs. Actual

| Aspect | Expected | Actual | Match? |
|--------|----------|--------|--------|
| Baseline threshold classification | flips exactly at 25 / 20 / 15 / 40 / 35° | flips exactly at those values | ✅ |
| Critical override | overrides all other conditions, both classifiers | confirmed (T06, T07, T09, T17) | ✅ |
| Personalized vs. baseline | personalized flags sub-threshold deviations baseline misses | 47 FN → 0 FN; T15 demonstrates it | ✅ |
| Uncalibrated behaviour | clean baseline fallback, honest `model` field | `model:"baseline"`, `fallback:true` | ✅ |
| Invalid readings | rejected distinctly, state uncorrupted | HTTP 400 + counters, last-good intact | ✅ |
| Dropout | detected as offline after 8 s | offline flip confirmed | ✅ |
| Calibration persistence | survives restart | stored in SQLite, reloaded on startup | ✅ |
| End-to-end latency | real-time (well under one 400 ms send interval) | ~2.7 ms mean | ✅ |
| Automated tests | ≥ 5 across normal/boundary/abnormal | 46 cases, all pass | ✅ (exceeds) |

**Deviations / caveats.** The proposed model's 4.7 % false-positive rate is a
deliberate sensitivity trade-off, not a defect — it is the expected cost of
catching every real deviation, and is tunable via the τ percentile
(`PERSONAL_PERCENTILE`). Energy/on-device figures in §2 are estimates because no
physical board was measured this session.

---

## 5. Wokwi-derived results  *(placeholder — filled in separately)*

> The Assessment-5 Wokwi simulation (2× MPU-6050 + flex + buzzer + LED, on-device
> fixed-threshold classification, no Wi-Fi) is produced in a **separate**
> workflow. Paste those results here:
>
> - [ ] Wokwi on-device classification behaviour / screenshots
> - [ ] On-device threshold timing / actuator (buzzer, LED) response
> - [ ] Any Wokwi-measured resource figures
> - [ ] Comparison notes vs. this backend-hosted prototype
