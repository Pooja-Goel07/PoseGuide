"""
PoseGuide - performance benchmark (feeds results.md)
====================================================

Measures REAL numbers for the baseline vs. proposed comparison:
  * classification accuracy vs. the generator's ground-truth state
  * problem-detection rate (recall) and false-positive rate
  * end-to-end HTTP response time (via TestClient)
  * classifier compute time and workload memory (tracemalloc)

Usage:  python -m tools.benchmark
"""

from __future__ import annotations

import csv
import os
import statistics
import time
import tracemalloc

import numpy as np

from ml import extract_features, classify_baseline, classify_personalized
from ml.personalized import fit_personal_model

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "poseguide_dataset.csv")

STATE_TO_CONDITION = {
    "normal": "good",
    "slouch": "slouching",
    "forward_head": "forward_head",
    "lateral_lean": "lateral_lean",
    "critical": "critical",
}


def load_rows():
    with open(DATA) as f:
        return list(csv.DictReader(f))


def features_of(row):
    return extract_features(
        float(row["torso_pitch"]), float(row["torso_roll"]), float(row["neck_pitch"])
    )


def bench_baseline(rows):
    correct = 0
    tp = fp = tn = fn = 0
    for r in rows:
        x = features_of(r)
        pred = classify_baseline(x)["condition"]
        state = r["state"]
        expected = STATE_TO_CONDITION[state]

        # exact-label accuracy (multiple_issues counts as a detected problem, not a match)
        if pred == expected:
            correct += 1

        actual_problem = state != "normal"
        pred_problem = pred != "good"
        if actual_problem and pred_problem:
            tp += 1
        elif actual_problem and not pred_problem:
            fn += 1
        elif not actual_problem and pred_problem:
            fp += 1
        else:
            tn += 1
    return metrics(correct, len(rows), tp, fp, tn, fn)


def bench_personalized(rows):
    # Calibrate on a clean neutral subset (first 300 'normal' rows).
    calib = [features_of(r) for r in rows if r["state"] == "normal"][:300]
    model = fit_personal_model(np.array(calib))

    correct = 0  # "did it agree the reading is normal vs a problem"
    tp = fp = tn = fn = 0
    for r in rows:
        x = features_of(r)
        cond = classify_personalized(x, model)["condition"]
        state = r["state"]
        actual_problem = state != "normal"
        pred_problem = cond in ("personalized_deviation", "critical")
        if actual_problem == pred_problem:
            correct += 1
        if actual_problem and pred_problem:
            tp += 1
        elif actual_problem and not pred_problem:
            fn += 1
        elif not actual_problem and pred_problem:
            fp += 1
        else:
            tn += 1
    return metrics(correct, len(rows), tp, fp, tn, fn), model


def metrics(correct, total, tp, fp, tn, fn):
    detection = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    return {
        "accuracy": correct / total,
        "detection_rate": detection,
        "false_positive_rate": fpr,
        "precision": precision,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
    }


def bench_latency(rows, n=500):
    # Pure classifier compute time.
    xs = [features_of(r) for r in rows[:n]]
    t0 = time.perf_counter()
    for x in xs:
        classify_baseline(x)
    base_compute = (time.perf_counter() - t0) / len(xs) * 1000

    model = fit_personal_model(np.array([features_of(r) for r in rows if r["state"] == "normal"][:300]))
    t0 = time.perf_counter()
    for x in xs:
        classify_personalized(x, model)
    pers_compute = (time.perf_counter() - t0) / len(xs) * 1000

    # End-to-end HTTP round trip via TestClient.
    from fastapi.testclient import TestClient
    import main
    main.reset_state()
    with TestClient(main.app) as c:
        samples = []
        for r in rows[:n]:
            payload = {"torso": {"pitch": float(r["torso_pitch"]), "roll": float(r["torso_roll"])},
                       "neck": {"pitch": float(r["neck_pitch"])}}
            t0 = time.perf_counter()
            c.post("/api/sensor-data", json=payload)
            samples.append((time.perf_counter() - t0) * 1000)
    return base_compute, pers_compute, samples


def main_run():
    rows = load_rows()
    print(f"dataset rows: {len(rows)}\n")

    tracemalloc.start()
    base = bench_baseline(rows)
    (pers, _model) = bench_personalized(rows)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    def show(name, m):
        print(f"[{name}]")
        print(f"  accuracy            : {m['accuracy']*100:.1f}%")
        print(f"  detection rate      : {m['detection_rate']*100:.1f}%")
        print(f"  false-positive rate : {m['false_positive_rate']*100:.1f}%")
        print(f"  precision           : {m['precision']*100:.1f}%")
        print(f"  confusion tp/fp/tn/fn: {m['tp']}/{m['fp']}/{m['tn']}/{m['fn']}\n")

    show("BASELINE  (fixed threshold)", base)
    show("PROPOSED  (personalized)", pers)

    base_c, pers_c, http = bench_latency(rows)
    print("[response time]")
    print(f"  baseline compute      : {base_c:.4f} ms/reading")
    print(f"  personalized compute  : {pers_c:.4f} ms/reading")
    print(f"  end-to-end HTTP mean  : {statistics.mean(http):.3f} ms")
    print(f"  end-to-end HTTP median: {statistics.median(http):.3f} ms")
    print(f"  end-to-end HTTP p95   : {sorted(http)[int(len(http)*0.95)]:.3f} ms")
    print(f"\n[resource] classification workload peak memory: {peak/1024:.1f} KiB")


if __name__ == "__main__":
    main_run()
