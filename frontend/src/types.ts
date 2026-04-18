export type SettingsResponse = {
  app_name: string;
  source_mode: "mock" | "aaronia";
  default_frequency_from_hz: number;
  default_frequency_to_hz: number;
  default_bins: number;
  default_capture_seconds: number;
  max_capture_samples: number;
  ai_model: string;
  ai_explanation_enabled: boolean;
};

export type DensityRequest = {
  frequency_from_hz: number;
  frequency_to_hz: number;
  bins: number;
  capture_seconds: number;
  reference_level_dbm: number | null;
  occupancy_threshold_db: number;
  apply_to_device: boolean;
  include_bins: boolean;
  window: "hann" | "rectangular";
};

export type BinDensity = {
  index: number;
  frequency_hz: number;
  density_linear: number;
  density_db_per_hz: number;
  power_linear: number;
  power_db: number;
};

export type DensitySummary = {
  frequency_from_hz: number;
  frequency_to_hz: number;
  center_frequency_hz: number;
  span_hz: number;
  sample_rate_hz: number;
  sample_count: number;
  bin_count: number;
  bin_width_hz: number;
  averaged_segments: number;
  density_unit: string;
  power_unit: string;
  mean_density_linear: number;
  mean_density_db_per_hz: number;
  peak_density_linear: number;
  peak_density_db_per_hz: number;
  peak_frequency_hz: number;
  integrated_power_linear: number;
  integrated_power_db: number;
};

export type CaptureSettings = {
  frequency_from_hz: number;
  frequency_to_hz: number;
  center_frequency_hz: number;
  span_hz: number;
  rbw_estimate_hz: number;
  sample_rate_hz: number;
  bins: number;
  reference_level_dbm: number | null;
  occupancy_threshold_db: number;
  capture_seconds: number;
  window: "hann" | "rectangular";
};

export type RangeAssessment = {
  method: string;
  threshold_offset_db: number;
  noise_floor_db_per_hz: number;
  threshold_db_per_hz: number;
  occupied_bins: number;
  occupancy_percent: number;
  occupied_bandwidth_hz: number;
  mean_excess_db: number;
  peak_to_floor_db: number;
  label: "quiet" | "sparse" | "moderate" | "dense";
};

export type DensityResponse = {
  source: "mock" | "aaronia";
  configured_device: boolean;
  summary: DensitySummary;
  capture_settings: CaptureSettings;
  range_assessment: RangeAssessment;
  bins: BinDensity[];
  metadata: Record<string, string | number | boolean | null>;
};

export type DeviceSetting = {
  label: string;
  value: string | number | boolean | null;
  raw_value: string | number | boolean | null;
  unit: string | null;
  path: string | null;
};

export type DeviceStreamStatus = {
  payload: string | null;
  unit: string | null;
  frequency_from_hz: number | null;
  frequency_to_hz: number | null;
  center_frequency_hz: number | null;
  span_hz: number | null;
  sample_frequency_hz: number | null;
  samples_per_packet: number | null;
  sample_size: number | null;
  sample_depth: number | null;
  scale: number | null;
  rbw_from_fft_size_hz: number | null;
};

export type DeviceStatusResponse = {
  source: "mock" | "aaronia";
  reachable: boolean;
  endpoints: Record<string, string>;
  info: Record<string, string | number | boolean | null>;
  inputs: string[];
  health_state: string | null;
  stream: DeviceStreamStatus | null;
  settings: Record<string, DeviceSetting>;
  error: string | null;
};

export type MeasurementCreate = {
  name: string | null;
  result: DensityResponse;
  device_status: DeviceStatusResponse | null;
};

export type MeasurementSummary = {
  id: string;
  name: string;
  created_at: string;
  source: "mock" | "aaronia";
  frequency_from_hz: number;
  frequency_to_hz: number;
  center_frequency_hz: number;
  span_hz: number;
  bins: number;
  occupancy_percent: number;
  occupied_bandwidth_hz: number;
  mean_density_db_per_hz: number;
  peak_density_db_per_hz: number;
  integrated_power_db: number;
  peak_frequency_hz: number;
  bins_count: number;
};

export type MeasurementStored = MeasurementSummary & {
  result: DensityResponse;
  device_status: DeviceStatusResponse | null;
};

export type AIComparisonRequest = {
  baseline_name: string | null;
  comparison_name: string | null;
  response_language: "en" | "uk";
  baseline: DensityResponse;
  comparison: DensityResponse;
};

export type AIComparisonResponse = {
  provider: string;
  model: string;
  winner: "baseline" | "comparison" | "tie" | "unclear";
  winner_name: string;
  comparison_quality: "direct" | "caution";
  numeric_basis: string;
  caveats: string[];
  explanation: string;
};
