import type { Classification } from "../api";
import { label, color } from "../labels";

interface Props {
  title: string;
  subtitle: string;
  data?: Classification;
}

/** One classifier's live verdict. Rendered twice, side by side, for comparison. */
export default function ClassifierCard({ title, subtitle, data }: Props) {
  const condition = data?.condition ?? "";
  const c = condition ? color(condition) : "#334155";
  const isPersonalized = data?.model === "personalized";
  const usingFallback = data?.fallback === true;

  return (
    <div className="card classifier-card" style={{ borderTop: `3px solid ${c}` }}>
      <div className="classifier-head">
        <div>
          <h3>{title}</h3>
          <span className="muted small">{subtitle}</span>
        </div>
        {data && (
          <span className="model-badge" data-fallback={usingFallback}>
            {usingFallback ? "baseline (fallback)" : data.model}
          </span>
        )}
      </div>

      <div className="condition-line">
        <span className="condition-dot" style={{ background: c }} />
        <span className="condition-name" style={{ color: c }}>
          {condition ? label(condition) : "—"}
        </span>
      </div>

      <div className="score-row">
        <div className="score-num">{data ? data.score : "—"}</div>
        <div className="muted small">posture score / 100</div>
      </div>

      {isPersonalized && !usingFallback && (
        <div className="mahal-row">
          <div>
            <div className="muted small">Mahalanobis D</div>
            <div className="mono">{data?.mahalanobis?.toFixed(2) ?? "—"}</div>
          </div>
          <div>
            <div className="muted small">threshold τ</div>
            <div className="mono">{data?.tau?.toFixed(2) ?? "—"}</div>
          </div>
        </div>
      )}

      <ul className="warnings">
        {data && data.warnings.length > 0 ? (
          data.warnings.map((w, i) => <li key={i}>{w}</li>)
        ) : (
          <li className="muted">No warnings</li>
        )}
      </ul>
    </div>
  );
}
