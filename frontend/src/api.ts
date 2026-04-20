import type {
  AIComparisonRequest,
  AIComparisonResponse,
  ConductedJammerComparisonRequest,
  ConductedJammerComparisonResponse,
  DensityRequest,
  DensityResponse,
  DeviceStatusResponse,
  MeasurementCreate,
  MeasurementStored,
  MeasurementSummary,
  SettingsResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(errorBody?.detail ?? `HTTP ${response.status}`);
  }

  return (await response.json()) as T;
}

export function getSettings(): Promise<SettingsResponse> {
  return requestJson<SettingsResponse>("/api/settings");
}

export function getDeviceStatus(): Promise<DeviceStatusResponse> {
  return requestJson<DeviceStatusResponse>("/api/device/status");
}

export function calculateDensity(payload: DensityRequest): Promise<DensityResponse> {
  return requestJson<DensityResponse>("/api/density", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listMeasurements(): Promise<MeasurementSummary[]> {
  return requestJson<MeasurementSummary[]>("/api/measurements");
}

export function createMeasurement(payload: MeasurementCreate): Promise<MeasurementStored> {
  return requestJson<MeasurementStored>("/api/measurements", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMeasurement(id: string): Promise<MeasurementStored> {
  return requestJson<MeasurementStored>(`/api/measurements/${id}`);
}

export function deleteMeasurement(id: string): Promise<{ deleted: boolean }> {
  return requestJson<{ deleted: boolean }>(`/api/measurements/${id}`, {
    method: "DELETE",
  });
}

export function explainComparison(payload: AIComparisonRequest): Promise<AIComparisonResponse> {
  return requestJson<AIComparisonResponse>("/api/comparisons/ai-explanation", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function compareConductedJammers(
  payload: ConductedJammerComparisonRequest,
): Promise<ConductedJammerComparisonResponse> {
  return requestJson<ConductedJammerComparisonResponse>("/api/jammer/compare-conducted", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
