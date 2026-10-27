import { useState } from "react";
import { api, type CalibrationStatus } from "../api";

interface Props {
  calib?: CalibrationStatus;
  onChange: () => void; // ask parent to refresh status immediately
}

/**
 * Calibration control: start/stop the personalization window and show live
 * progress (samples collected) and the resulting threshold tau.
 */
export default function CalibrationPanel({ calib, onChange }: Props) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const calibrating = calib?.calibrating ?? false;
  const collected = calib?.samples_collected ?? 0;
  const required = calib?.min_required ?? 30;
  const pct = Math.min(100, Math.round((collected / required) * 100));

  async function start() {
    setBusy(true);
    setMessage(null);
    try {
      await api.calibrateStart();
      setMessage("Calibration started — sit in your normal neutral posture.");
    } finally {
      setBusy(false);
      onChange();
    }
  }

  async function stop() {
    setBusy(true);
    try {
      const res = await api.calibrateStop();
      if (res.calibrated) {
        setMessage(`Calibrated ✓  τ = ${res.tau?.toFixed(2)}  (${res.n_samples} samples)`);
      } else {
        setMessage(`Not calibrated — ${res.reason ?? "too few samples"}`);
      }
    } finally {
      setBusy(false);
      onChange();
    }
  }

  async function reset() {
    setBusy(true);
    try {
      await api.calibrateReset();
      setMessage("Calibration cleared — personalized model reverts to baseline fallback.");
    } finally {
      setBusy(false);
      onChange();
    }
  }

  return (
    <div className="card calibration">
      <div className="classifier-head">
        <h3>Personalization / Calibration</h3>
        {calib?.calibrated && !calibrating && (
          <span className="model-badge">τ = {calib.tau?.toFixed(2)}</span>
        )}
      </div>

      {calibrating ? (
        <>
          <div className="muted small">
            Collecting… {collected} / {required} samples
          </div>
          <div className="progress">
            <div className="progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="btn-row">
            <button className="btn primary" disabled={busy} onClick={stop}>
              Stop &amp; Fit Model
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="muted small">
            {calib?.calibrated
              ? `Personalized model active (${calib.n_samples} samples).`
              : "No personalized model yet — both cards show the baseline classifier."}
          </div>
          <div className="btn-row">
            <button className="btn primary" disabled={busy} onClick={start}>
              Start Calibration
            </button>
            {calib?.calibrated && (
              <button className="btn ghost" disabled={busy} onClick={reset}>
                Reset
              </button>
            )}
          </div>
        </>
      )}

      {message && <div className="calib-msg">{message}</div>}
    </div>
  );
}
