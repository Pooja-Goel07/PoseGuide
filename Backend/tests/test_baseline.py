"""
Baseline classifier tests: normal, boundary (exactly at/just past each
threshold), abnormal. Verifies each classification flips exactly where it
should (25 / 20 / 15 / 40 / 35 deg).
"""

import pytest

from ml import extract_features, classify_baseline


def cond(torso_pitch, torso_roll, neck_pitch):
    return classify_baseline(extract_features(torso_pitch, torso_roll, neck_pitch))["condition"]


# ── Normal ──────────────────────────────────────────────────────────────
def test_good_posture():
    assert cond(2.0, 1.0, 7.0) == "good"


# ── Boundary: slouch at 25 deg torso pitch ──────────────────────────────
@pytest.mark.parametrize(
    "pitch,expected",
    [(25.0, "good"), (24.9, "good"), (25.1, "slouching"), (26.0, "slouching")],
)
def test_slouch_boundary(pitch, expected):
    # neck_pitch chosen so neck_relative stays < 20 (no forward-head trigger)
    assert cond(pitch, 0.0, pitch + 5.0) == expected


# ── Boundary: forward head at 20 deg neck-relative ──────────────────────
@pytest.mark.parametrize(
    "neck_rel,expected",
    [(20.0, "good"), (19.9, "good"), (20.1, "forward_head"), (25.0, "forward_head")],
)
def test_forward_head_boundary(neck_rel, expected):
    assert cond(5.0, 0.0, 5.0 + neck_rel) == expected


# ── Boundary: lateral lean at 15 deg torso roll ─────────────────────────
@pytest.mark.parametrize(
    "roll,expected",
    [(15.0, "good"), (14.9, "good"), (15.1, "lateral_lean"), (-16.0, "lateral_lean")],
)
def test_lateral_lean_boundary(roll, expected):
    assert cond(4.0, roll, 9.0) == expected


# ── Boundary: critical override at 40 deg pitch / 35 deg neck ────────────
@pytest.mark.parametrize(
    "pitch,expected",
    [(40.0, "slouching"), (40.1, "critical"), (45.0, "critical")],
)
def test_critical_pitch_boundary(pitch, expected):
    assert cond(pitch, 0.0, pitch + 5.0) == expected


@pytest.mark.parametrize(
    "neck_rel,expected",
    [(35.0, "forward_head"), (35.1, "critical"), (40.0, "critical")],
)
def test_critical_neck_boundary(neck_rel, expected):
    assert cond(5.0, 0.0, 5.0 + neck_rel) == expected


# ── Abnormal: multiple simultaneous issues ──────────────────────────────
def test_multiple_issues():
    # slouch (30) + lateral lean (18), neck kept low
    assert cond(30.0, 18.0, 33.0) == "multiple_issues"


# ── Critical overrides multiple issues ──────────────────────────────────
def test_critical_overrides_multiple():
    # would be multiple issues, but pitch 45 forces critical
    assert cond(45.0, 18.0, 48.0) == "critical"


# ── Score sanity ────────────────────────────────────────────────────────
def test_perfect_score_for_good():
    res = classify_baseline(extract_features(0.0, 0.0, 0.0))
    assert res["score"] == 100


def test_score_decreases_with_deviation():
    good = classify_baseline(extract_features(2.0, 1.0, 7.0))["score"]
    bad = classify_baseline(extract_features(35.0, 20.0, 60.0))["score"]
    assert bad < good
