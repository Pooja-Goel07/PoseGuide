// PoseGuide - backend API client + shared types.

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

export interface Classification {
  model: "baseline" | "personalized";
  condition: string;
  score: number;
  warnings: string[];
  angles: {
    torso_pitch: number;
    torso_roll: number;
    neck_relative_pitch: number;
  };
  mahalanobis?: number;
  tau?: number;
  n_calibration_samples?: number;
  fallback?: boolean;
  reason?: string;
}

export interface SensorResult {
  status: string;
  timestamp: number;
  torso_pitch: number;
  torso_roll: number;
  neck_relative_pitch: number;
  baseline: Classification;
  personalized: Classification;
}

export interface SystemStatus {
  sensor_online: boolean;
  last_seen: string | null;
  seconds_since_last: number | null;
  timeout_seconds: number;
  total_readings: number;
  invalid_readings: number;
  last_error: string | null;
  calibrated: boolean;
  calibrating: boolean;
  tau: number | null;
  calibration_samples: number;
}

export interface CalibrationStatus {
  calibrating: boolean;
  samples_collected: number;
  min_required: number;
  calibrated: boolean;
  tau: number | null;
  n_samples: number;
}

export interface HistoryRow {
  id: number;
  timestamp: string;
  torso_pitch: number;
  torso_roll: number;
  neck_relative_pitch: number;
  baseline_condition: string;
  baseline_score: number;
  personalized_condition: string;
  personalized_model: string;
  mahalanobis: number | null;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function postJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  latest: () => getJSON<SensorResult | { data: null; message: string }>("/api/latest"),
  status: () => getJSON<SystemStatus>("/api/status"),
  history: (limit = 120) => getJSON<HistoryRow[]>(`/api/history?limit=${limit}`),
  calibrateStatus: () => getJSON<CalibrationStatus>("/api/calibrate/status"),
  calibrateStart: () => postJSON<unknown>("/api/calibrate/start"),
  calibrateStop: () => postJSON<{ calibrated: boolean; tau?: number; n_samples?: number; reason?: string }>(
    "/api/calibrate/stop",
  ),
  calibrateReset: () => postJSON<unknown>("/api/calibrate/reset"),
};

export function isSensorResult(x: unknown): x is SensorResult {
  return !!x && typeof x === "object" && "baseline" in x && "personalized" in x;
}
