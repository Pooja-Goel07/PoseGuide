import type { SensorResult } from "../api";

interface Props {
  data?: SensorResult;
}

const GAUGES = [
  { key: "torso_pitch", label: "Torso Pitch", unit: "°", max: 60, signed: true },
  { key: "torso_roll", label: "Torso Roll", unit: "°", max: 40, signed: true },
  { key: "neck_relative_pitch", label: "Neck (relative)", unit: "°", max: 50, signed: false },
] as const;

/** Live numeric angle readouts with a proportional bar. */
export default function AngleGauges({ data }: Props) {
  return (
    <div className="gauges">
      {GAUGES.map((g) => {
        const raw = data ? (data[g.key] as number) : 0;
        const mag = Math.abs(raw);
        const pct = Math.min(100, (mag / g.max) * 100);
        return (
          <div className="gauge" key={g.key}>
            <div className="gauge-top">
              <span className="muted small">{g.label}</span>
              <span className="gauge-val mono">
                {data ? raw.toFixed(1) : "—"}
                {g.unit}
              </span>
            </div>
            <div className="gauge-track">
              <div className="gauge-fill" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
