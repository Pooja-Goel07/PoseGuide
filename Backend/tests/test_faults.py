"""
Fault-handling tests (Assessment-6 requires >=2 demonstrated fault conditions):

  Fault 1 - invalid/malformed readings are rejected distinctly from posture
            anomalies, and a burst of them does not corrupt good state.
  Fault 2 - sensor dropout is detected as "offline" after the timeout window.
"""

import time

import main
from ml.constants import SENSOR_TIMEOUT_SECONDS


def good_packet(pitch=2.0, roll=1.0, neck=7.0):
    return {"torso": {"pitch": pitch, "roll": roll}, "neck": {"pitch": neck}}


JSON = {"content-type": "application/json"}


# ── Fault 1: invalid readings rejected with distinct reasons ────────────
def test_reject_nan(client):
    # NaN literal in raw JSON (Python's json parser accepts the NaN token).
    r = client.post(
        "/api/sensor-data",
        content='{"torso":{"pitch":NaN,"roll":1.0},"neck":{"pitch":7.0}}',
        headers=JSON,
    )
    assert r.status_code == 400
    assert r.json()["reason"] == "non_finite"


def test_reject_out_of_range(client):
    r = client.post("/api/sensor-data", json=good_packet(pitch=500.0))
    assert r.status_code == 400
    assert r.json()["reason"] == "out_of_range"


def test_reject_missing_field(client):
    r = client.post("/api/sensor-data", json={"torso": {"pitch": 2.0}, "neck": {"pitch": 7.0}})
    assert r.status_code == 400
    assert r.json()["reason"] == "missing_field"


def test_reject_malformed_payload(client):
    r = client.post("/api/sensor-data", content="not-json", headers=JSON)
    assert r.status_code == 400
    assert r.json()["reason"] == "malformed_payload"


def test_invalid_reading_is_not_a_posture_anomaly(client):
    """A broken reading is a distinct fault, never silently classified."""
    before = client.get("/api/status").json()["total_readings"]
    client.post("/api/sensor-data", json=good_packet(pitch=99999.0))
    after = client.get("/api/status").json()
    assert after["total_readings"] == before          # not counted as a reading
    assert after["invalid_readings"] == 1             # counted as a fault
    assert after["last_error"].startswith("out_of_range")


def test_burst_of_invalid_does_not_corrupt_state(client):
    # 1) a good reading establishes valid state
    client.post("/api/sensor-data", json=good_packet(3.0, 1.0, 8.0))  # good
    # 2) a burst of assorted invalid payloads
    client.post("/api/sensor-data", content='{"torso":{"pitch":NaN,"roll":0},"neck":{"pitch":0}}', headers=JSON)
    client.post("/api/sensor-data", json=good_packet(pitch=400.0))
    client.post("/api/sensor-data", json={"bogus": True})
    client.post("/api/sensor-data", content="garbage", headers=JSON)
    # 3) a good reading still classifies correctly; last-good state intact
    body = client.post("/api/sensor-data", json=good_packet(30.0, 2.0, 35.0)).json()  # slouch
    assert body["baseline"]["condition"] == "slouching"

    status = client.get("/api/status").json()
    assert status["total_readings"] == 2       # only the two valid ones
    assert status["invalid_readings"] == 4     # the four bad ones
    assert client.get("/api/latest").json()["baseline"]["condition"] == "slouching"


# ── Fault 2: dropout / staleness -> sensor offline ──────────────────────
def test_sensor_online_after_valid_reading(client):
    client.post("/api/sensor-data", json=good_packet())
    assert client.get("/api/status").json()["sensor_online"] is True


def test_sensor_offline_after_timeout(client):
    client.post("/api/sensor-data", json=good_packet())
    # Simulate a dropout: rewind the last-seen clock past the timeout window.
    main.STATE["last_valid_monotonic"] = time.monotonic() - (SENSOR_TIMEOUT_SECONDS + 5)
    status = client.get("/api/status").json()
    assert status["sensor_online"] is False
    assert status["seconds_since_last"] > SENSOR_TIMEOUT_SECONDS


def test_sensor_offline_before_any_reading(client):
    assert client.get("/api/status").json()["sensor_online"] is False
