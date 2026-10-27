// Human-readable labels + colors for posture conditions.

export const CONDITION_LABEL: Record<string, string> = {
  good: "Good",
  slouching: "Slouching",
  forward_head: "Forward Head",
  lateral_lean: "Lateral Lean",
  multiple_issues: "Multiple Issues",
  critical: "Critical",
  personalized_deviation: "Personalized Deviation",
};

// Semantic color per condition (works on the dark theme).
export const CONDITION_COLOR: Record<string, string> = {
  good: "#22c55e",
  slouching: "#f59e0b",
  forward_head: "#f59e0b",
  lateral_lean: "#f59e0b",
  multiple_issues: "#ef4444",
  critical: "#dc2626",
  personalized_deviation: "#a855f7",
};

export function label(condition: string): string {
  return CONDITION_LABEL[condition] ?? condition;
}

export function color(condition: string): string {
  return CONDITION_COLOR[condition] ?? "#94a3b8";
}
