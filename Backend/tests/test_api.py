"""
API-level tests via FastAPI TestClient: valid ingest, dual-classifier response,
the latest cache, and the full calibration workflow through the HTTP layer.
"""


def good_packet(pitch=2.0, roll=1.0, neck=7.0):
    return {"torso": {"pitch": pitch, "roll": roll}, "neck": {"pitch": neck}, "timestamp": 1}


def test_valid_reading_returns_both_classifiers(client):
    r = client.post("/api/sensor-data", json=good_packet())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["baseline"]["condition"] == "good"
    # No calibration yet -> personalized falls back to baseline honestly.
    assert body["personalized"]["model"] == "baseline"
    assert body["personalized"]["fallback"] is True


def test_latest_reflects_last_reading(client):
    client.post("/api/sensor-data", json=good_packet(30.0, 2.0, 35.0))  # slouch
    latest = client.get("/api/latest").json()
    assert latest["baseline"]["condition"] == "slouching"


def test_neck_relative_derived_server_side(client):
    # neck.pitch 30, torso.pitch 5 -> neck_relative = 25
    body = client.post("/api/sensor-data", json=good_packet(5.0, 0.0, 30.0)).json()
    assert body["neck_relative_pitch"] == 25.0


def test_status_endpoint_shape(client):
    client.post("/api/sensor-data", json=good_packet())
    s = client.get("/api/status").json()
    assert s["sensor_online"] is True
    assert s["total_readings"] == 1
    assert s["invalid_readings"] == 0
    assert s["calibrated"] is False


def test_calibration_workflow(client):
    # Start, feed a clean neutral baseline, stop -> model fitted.
    assert client.post("/api/calibrate/start").status_code == 200
    for i in range(60):
        # small deterministic variation around neutral
        client.post("/api/sensor-data", json=good_packet(3.0 + (i % 3), (i % 2), 8.0 + (i % 3)))
    stop = client.post("/api/calibrate/stop").json()
    assert stop["calibrated"] is True
    assert stop["tau"] > 0
    assert stop["n_samples"] == 60

    # Subsequent readings now run the personalized model.
    body = client.post("/api/sensor-data", json=good_packet(3.0, 0.0, 8.0)).json()
    assert body["personalized"]["model"] == "personalized"

    status = client.get("/api/status").json()
    assert status["calibrated"] is True


def test_calibration_too_few_samples_reports_uncalibrated(client):
    client.post("/api/calibrate/start")
    for _ in range(5):
        client.post("/api/sensor-data", json=good_packet())
    stop = client.post("/api/calibrate/stop").json()
    assert stop["calibrated"] is False


def test_history_endpoint(client):
    for _ in range(3):
        client.post("/api/sensor-data", json=good_packet())
    hist = client.get("/api/history?limit=10").json()
    assert len(hist) == 3
    assert "baseline_condition" in hist[0]
