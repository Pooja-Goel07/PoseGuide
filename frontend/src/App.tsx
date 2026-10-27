import { useCallback, useEffect, useState } from "react";
import {
  api,
  isSensorResult,
  type SensorResult,
  type SystemStatus,
  type CalibrationStatus,
  type HistoryRow,
} from "./api";
import { color } from "./labels";
import PostureAvatar from "./components/PostureAvatar";
import StatusBar from "./components/StatusBar";
import ClassifierCard from "./components/ClassifierCard";
import CalibrationPanel from "./components/CalibrationPanel";
import AngleGauges from "./components/AngleGauges";
import HistoryChart from "./components/HistoryChart";

export default function App() {
  const [latest, setLatest] = useState<SensorResult | undefined>();
  const [status, setStatus] = useState<SystemStatus | undefined>();
  const [calib, setCalib] = useState<CalibrationStatus | undefined>();
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [connected, setConnected] = useState(false);

  const refreshStatus = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([api.status(), api.calibrateStatus()]);
      setStatus(s);
      setCalib(c);
      setConnected(true);
    } catch {
      setConnected(false);
    }
  }, []);

  // Fast poll: latest reading.
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const r = await api.latest();
        if (isSensorResult(r)) setLatest(r);
        setConnected(true);
      } catch {
        setConnected(false);
      }
    }, 500);
    return () => clearInterval(id);
  }, []);

  // Medium poll: status + calibration.
  useEffect(() => {
    refreshStatus();
    const id = setInterval(refreshStatus, 1000);
    return () => clearInterval(id);
  }, [refreshStatus]);

  // Slow poll: history.
  useEffect(() => {
    const load = async () => {
      try {
        setHistory(await api.history(120));
      } catch {
        /* ignore */
      }
    };
    load();
    const id = setInterval(load, 2500);
    return () => clearInterval(id);
  }, []);

  const cond = latest?.baseline.condition ?? "";
  const avatarColor = cond ? color(cond) : "#334155";

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>PoseGuide</h1>
          <span className="muted small">
            Real-time posture monitoring · baseline vs. personalized model
          </span>
        </div>
        <div className="header-badge">Assessment-6 Prototype</div>
      </header>

      <StatusBar status={status} connected={connected} />

      <div className="grid">
        <section className="col-left">
          <div className="card avatar-card">
            <PostureAvatar
              torsoPitch={latest?.torso_pitch ?? 0}
              torsoRoll={latest?.torso_roll ?? 0}
              neckRelativePitch={latest?.neck_relative_pitch ?? 0}
              condition={cond}
              color={avatarColor}
            />
          </div>
          <div className="card">
            <h3 className="card-title">Live Sensor Angles</h3>
            <AngleGauges data={latest} />
          </div>
        </section>

        <section className="col-right">
          <div className="compare-grid">
            <ClassifierCard
              title="Baseline"
              subtitle="Fixed clinical thresholds"
              data={latest?.baseline}
            />
            <ClassifierCard
              title="Personalized"
              subtitle="Mahalanobis distance vs. your calibration"
              data={latest?.personalized}
            />
          </div>

          <CalibrationPanel calib={calib} onChange={refreshStatus} />

          <HistoryChart rows={history} tau={status?.tau ?? null} />
        </section>
      </div>

      <footer className="app-footer muted small">
        Personalized model hosted in the backend (documented scope reduction) ·
        3-feature model [torso_pitch, torso_roll, neck_relative_pitch] · HTTP POST transport
      </footer>
    </div>
  );
}
