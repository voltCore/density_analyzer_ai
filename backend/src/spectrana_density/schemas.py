from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, model_validator


class DensityRequest(BaseModel):
    center_frequency_hz: float = Field(gt=0, description="Center frequency in Hz.")
    iq_rate_hz: float = Field(gt=0, description="IQ sample rate / span in Hz.")
    bins: int = Field(default=1024, ge=16, le=65_536)
    capture_seconds: float = Field(default=0.25, gt=0, le=30)
    reference_level_dbm: float | None = Field(default=None, ge=-200, le=80)
    occupancy_threshold_db: float = Field(default=6.0, ge=0.1, le=60)
    apply_to_device: bool = True
    include_bins: bool = True
    window: Literal["hann", "rectangular"] = "hann"

    @model_validator(mode="before")
    @classmethod
    def normalize_frequency_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        values = dict(data)
        center_hz = _number_or_none(values.get("center_frequency_hz"))
        iq_rate_hz = _first_number(
            values.get("iq_rate_hz"),
            values.get("iq_rate"),
            values.get("sample_rate_hz"),
            values.get("span_hz"),
        )
        frequency_from_hz = _number_or_none(values.get("frequency_from_hz"))
        frequency_to_hz = _number_or_none(values.get("frequency_to_hz"))

        if frequency_from_hz is not None and frequency_to_hz is not None:
            center_hz = (
                center_hz if center_hz is not None else (frequency_from_hz + frequency_to_hz) / 2
            )
            iq_rate_hz = (
                iq_rate_hz if iq_rate_hz is not None else frequency_to_hz - frequency_from_hz
            )

        if center_hz is not None:
            values["center_frequency_hz"] = center_hz
        if iq_rate_hz is not None:
            values["iq_rate_hz"] = iq_rate_hz

        return values

    @model_validator(mode="after")
    def validate_frequency_range(self) -> "DensityRequest":
        if self.frequency_to_hz <= self.frequency_from_hz:
            raise ValueError("frequency_to_hz must be greater than frequency_from_hz")
        return self

    @computed_field
    @property
    def frequency_from_hz(self) -> float:
        return self.center_frequency_hz - self.iq_rate_hz / 2

    @computed_field
    @property
    def frequency_to_hz(self) -> float:
        return self.center_frequency_hz + self.iq_rate_hz / 2

    @computed_field
    @property
    def span_hz(self) -> float:
        return self.iq_rate_hz


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _first_number(*values: Any) -> float | None:
    for value in values:
        parsed = _number_or_none(value)
        if parsed is not None:
            return parsed
    return None


def _normalize_iq_rate_hz(data: Any) -> Any:
    if not isinstance(data, dict):
        return data

    values = dict(data)
    if _number_or_none(values.get("iq_rate_hz")) is None:
        iq_rate_hz = _first_number(values.get("sample_rate_hz"), values.get("span_hz"))
        if iq_rate_hz is not None:
            values["iq_rate_hz"] = iq_rate_hz
    return values


class BinDensity(BaseModel):
    index: int
    frequency_hz: float
    density_linear: float
    density_db_per_hz: float
    power_linear: float
    power_db: float


class DensitySummary(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def normalize_iq_rate_hz(cls, data: Any) -> Any:
        return _normalize_iq_rate_hz(data)

    frequency_from_hz: float
    frequency_to_hz: float
    center_frequency_hz: float
    span_hz: float
    iq_rate_hz: float
    sample_rate_hz: float
    sample_count: int
    bin_count: int
    bin_width_hz: float
    averaged_segments: int
    density_unit: str
    power_unit: str
    mean_density_linear: float
    mean_density_db_per_hz: float
    peak_density_linear: float
    peak_density_db_per_hz: float
    peak_frequency_hz: float
    integrated_power_linear: float
    integrated_power_db: float


class CaptureSettings(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def normalize_iq_rate_hz(cls, data: Any) -> Any:
        return _normalize_iq_rate_hz(data)

    frequency_from_hz: float
    frequency_to_hz: float
    center_frequency_hz: float
    span_hz: float
    iq_rate_hz: float
    rbw_estimate_hz: float
    sample_rate_hz: float
    bins: int
    reference_level_dbm: float | None = None
    occupancy_threshold_db: float
    capture_seconds: float
    window: Literal["hann", "rectangular"]


class RangeAssessment(BaseModel):
    method: str
    threshold_offset_db: float
    noise_floor_db_per_hz: float
    threshold_db_per_hz: float
    occupied_bins: int
    occupancy_percent: float
    occupied_bandwidth_hz: float
    mean_excess_db: float
    peak_to_floor_db: float
    label: Literal["quiet", "sparse", "moderate", "dense"]


class DensityResponse(BaseModel):
    source: Literal["mock", "aaronia"]
    configured_device: bool
    summary: DensitySummary
    capture_settings: CaptureSettings
    range_assessment: RangeAssessment
    bins: list[BinDensity] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class DeviceSetting(BaseModel):
    label: str
    value: str | int | float | bool | None
    raw_value: str | int | float | bool | None = None
    unit: str | None = None
    path: str | None = None
    options: list[str | int | float | bool | None] = Field(default_factory=list)


class DeviceStreamStatus(BaseModel):
    payload: str | None = None
    unit: str | None = None
    frequency_from_hz: float | None = None
    frequency_to_hz: float | None = None
    center_frequency_hz: float | None = None
    span_hz: float | None = None
    iq_rate_hz: float | None = None
    iq_rate_options_hz: list[float] = Field(default_factory=list)
    sample_frequency_hz: float | None = None
    samples_per_packet: int | None = None
    sample_size: int | None = None
    sample_depth: int | None = None
    scale: float | None = None
    rbw_from_fft_size_hz: float | None = None


class DeviceStatusResponse(BaseModel):
    source: Literal["mock", "aaronia"]
    reachable: bool
    endpoints: dict[str, str]
    info: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    inputs: list[str] = Field(default_factory=list)
    health_state: str | None = None
    stream: DeviceStreamStatus | None = None
    settings: dict[str, DeviceSetting] = Field(default_factory=dict)
    error: str | None = None


class SettingsResponse(BaseModel):
    app_name: str
    source_mode: Literal["mock", "aaronia"]
    default_frequency_from_hz: float
    default_frequency_to_hz: float
    default_center_frequency_hz: float
    default_iq_rate_hz: float
    default_bins: int
    default_capture_seconds: float
    max_capture_samples: int
    ai_model: str
    ai_explanation_enabled: bool


class MeasurementCreate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    result: DensityResponse
    device_status: DeviceStatusResponse | None = None


class MeasurementSummary(BaseModel):
    id: str
    name: str
    created_at: str
    source: Literal["mock", "aaronia"]
    frequency_from_hz: float
    frequency_to_hz: float
    center_frequency_hz: float
    span_hz: float
    bins: int
    occupancy_percent: float
    occupied_bandwidth_hz: float
    mean_density_db_per_hz: float
    peak_density_db_per_hz: float
    integrated_power_db: float
    peak_frequency_hz: float
    bins_count: int


class MeasurementStored(MeasurementSummary):
    result: DensityResponse
    device_status: DeviceStatusResponse | None = None


SignalComparisonWinner = Literal["baseline", "comparison", "tie", "unclear"]


class AIComparisonRequest(BaseModel):
    baseline_name: str | None = Field(default=None, max_length=160)
    comparison_name: str | None = Field(default=None, max_length=160)
    response_language: Literal["en", "uk"] = "en"
    baseline: DensityResponse
    comparison: DensityResponse


class AIComparisonResponse(BaseModel):
    provider: str
    model: str
    winner: SignalComparisonWinner
    winner_name: str
    comparison_quality: Literal["direct", "caution"]
    numeric_basis: str
    caveats: list[str]
    explanation: str
