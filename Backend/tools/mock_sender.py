"""
PoseGuide - Python mock hardware sender
=======================================

A stand-in for the ESP32 firmware for when no board is flashed. It POSTs
plausible 3-feature readings to the running backend using the SAME synthetic
generator (ml.features) the firmware mirrors, so the live dashboard has
realistic data to show. It can also inject the same two fault conditions.

Usage:
    python -m tools.mock_sender                       # stream normal-ish data
    python -m tools.mock_sender --url http://localhost:8000
    python -m tools.mock_sender --rate 0.4            # seconds between sends
    python -m tools.mock_sender --faults              # enable invalid + dropout
    python -m tools.mock_sender --state normal --count 60   # steady state (calibration)

Tip: run  --state normal --count 60  while a calibration session is active to
feed the personalized model a clean neutral baseline.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.features import sample_reading, sample_state  # noqa: E402

INVALID_EVERY_N = 40
DROPOUT_EVERY_N = 120


def post(url: str, payload: dict) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url + "/api/sensor-data", data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:  # network error
        return -1, str(e)


def main():
    ap = argparse.ArgumentParser(description="PoseGuide mock hardware sender")
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--rate", type=float, default=0.4, help="seconds between sends")
    ap.add_argument("--faults", action="store_true", help="inject invalid + dropout faults")
    ap.add_argument("--state", default=None,
                    help="force a single posture state (normal/slouch/forward_head/lateral_lean/critical)")
    ap.add_argument("--count", type=int, default=0, help="stop after N readings (0 = forever)")
    args = ap.parse_args()

    rng = random.Random()
    n = 0
    print(f"Sending mock readings -> {args.url}  (Ctrl+C to stop)")
    try:
        while args.count == 0 or n < args.count:
            n += 1

            # Fault B: dropout.
            if args.faults and n % DROPOUT_EVERY_N == 0:
                drop = rng.uniform(10, 20)
                print(f"[FAULT B] dropout - silent for {drop:.0f}s")
                time.sleep(drop)
                continue

            if args.state:
                r = sample_state(args.state, rng)
            else:
                r = sample_reading(rng)
            payload = {
                "torso": {"pitch": r["torso_pitch"], "roll": r["torso_roll"]},
                "neck": {"pitch": r["neck_pitch"]},
                "timestamp": int(time.time() * 1000),
            }

            # Fault A: corrupt the reading.
            if args.faults and n % INVALID_EVERY_N == 0:
                if (n // INVALID_EVERY_N) % 2 == 0:
                    payload["torso"]["pitch"] = 999.0
                    print("[FAULT A] out-of-range torso.pitch=999")
                else:
                    payload["torso"]["pitch"] = math.nan
                    print("[FAULT A] NaN torso.pitch")

            code, text = post(args.url, payload)
            tag = r.get("state", "?")
            if code == 200:
                body = json.loads(text)
                print(f"200 [{tag:12}] baseline={body['baseline']['condition']:16} "
                      f"personalized={body['personalized']['condition']}")
            else:
                print(f"{code} {text[:120]}")

            time.sleep(args.rate)
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    # json.dumps emits NaN as the literal `NaN` token, which the backend parses
    # and correctly rejects as non_finite -- that's the intended fault path.
    main()
