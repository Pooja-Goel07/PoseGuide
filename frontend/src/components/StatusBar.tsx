import type { ReactNode } from "react";
import type { SystemStatus } from "../api";

interface Props {
  status?: SystemStatus;
  connected: boolean;
}

/** Device/actuator + fault status strip along the top of the dashboard. */
export default function StatusBar({ status, connected }: Props) {
  const online = connected && status?.sensor_online;

  return (
    <div className="statusbar">
      <div className="status-pill" data-on={online ? "1" : "0"}>
        <span className="pulse" />
        {online ? "Sensor Online" : "Sensor Offline"}
      </div>

      <div className="status-metrics">
        <Metric label="Backend" value={connected ? "connected" : "unreachable"} bad={!connected} />
        <Metric label="Total readings" value={status?.total_readings ?? "—"} />
        <Metric
          label="Invalid rejected"
          value={status?.invalid_readings ?? "—"}
          bad={(status?.invalid_readings ?? 0) > 0}
        />
        <Metric
          label="Last seen"
          value={status?.seconds_since_last != null ? `${status.seconds_since_last.toFixed(1)}s ago` : "never"}
        />
        <Metric label="Calibrated" value={status?.calibrated ? "yes" : "no"} />
      </div>

      {status?.last_error && (
        <div className="last-error" title="Most recent rejected reading">
          ⚠ {status.last_error}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, bad }: { label: string; value: ReactNode; bad?: boolean }) {
  return (
    <div className="metric">
      <span className="muted small">{label}</span>
      <span className={bad ? "metric-val bad" : "metric-val"}>{value}</span>
    </div>
  );
}
