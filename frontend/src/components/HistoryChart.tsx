import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { HistoryRow } from "../api";

interface Props {
  rows: HistoryRow[];
  tau: number | null;
}

/** Time-series of posture score (left axis) and Mahalanobis distance (right). */
export default function HistoryChart({ rows, tau }: Props) {
  const data = rows.map((r) => ({
    t: r.timestamp?.slice(11, 19) ?? String(r.id),
    score: r.baseline_score,
    mahal: r.mahalanobis,
    tau,
  }));

  return (
    <div className="card chart-card">
      <div className="classifier-head">
        <h3>History — Score &amp; Deviation</h3>
        <span className="muted small">last {rows.length} readings</span>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
          <XAxis dataKey="t" tick={{ fill: "#64748b", fontSize: 11 }} minTickGap={40} />
          <YAxis
            yAxisId="score"
            domain={[0, 100]}
            tick={{ fill: "#64748b", fontSize: 11 }}
          />
          <YAxis
            yAxisId="mahal"
            orientation="right"
            tick={{ fill: "#64748b", fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
            labelStyle={{ color: "#cbd5e1" }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line
            yAxisId="score"
            type="monotone"
            dataKey="score"
            name="Posture score"
            stroke="#22c55e"
            dot={false}
            strokeWidth={2}
            isAnimationActive={false}
          />
          <Line
            yAxisId="mahal"
            type="monotone"
            dataKey="mahal"
            name="Mahalanobis D"
            stroke="#a855f7"
            dot={false}
            strokeWidth={2}
            isAnimationActive={false}
          />
          {tau != null && (
            <Line
              yAxisId="mahal"
              type="monotone"
              dataKey="tau"
              name="τ threshold"
              stroke="#f59e0b"
              strokeDasharray="5 4"
              dot={false}
              strokeWidth={1.5}
              isAnimationActive={false}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
