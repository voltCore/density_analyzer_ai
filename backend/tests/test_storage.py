from spectrana_density.schemas import (
    CaptureSettings,
    DensityResponse,
    DensitySummary,
    MeasurementCreate,
    RangeAssessment,
)
from spectrana_density.storage import MeasurementStore


def test_measurement_store_creates_auto_name_and_reads_full_snapshot(tmp_path) -> None:
    store = MeasurementStore(str(tmp_path / "measurements.sqlite3"))
    payload = MeasurementCreate(name=None, result=_density_response())

    saved = store.create(payload)
    listed = store.list()
    loaded = store.get(saved.id)

    assert saved.name.endswith("740.000-750.000 MHz · 12.500%")
    assert listed[0].id == saved.id
    assert loaded.result.summary.peak_frequency_hz == 745_000_000
    assert loaded.result.bins == []


def _density_response() -> DensityResponse:
    return DensityResponse(
        source="aaronia",
        configured_device=True,
        summary=DensitySummary(
            frequency_from_hz=740_000_000,
            frequency_to_hz=750_000_000,
            center_frequency_hz=745_000_000,
            span_hz=10_000_000,
            sample_rate_hz=10_000_000,
            sample_count=16_384,
            bin_count=1024,
            bin_width_hz=9765.625,
            averaged_segments=16,
            density_unit="V^2/Hz",
            power_unit="V^2",
            mean_density_linear=1.0,
            mean_density_db_per_hz=-44.5,
            peak_density_linear=2.0,
            peak_density_db_per_hz=-41.0,
            peak_frequency_hz=745_000_000,
            integrated_power_linear=3.0,
            integrated_power_db=16.2,
        ),
        capture_settings=CaptureSettings(
            frequency_from_hz=740_000_000,
            frequency_to_hz=750_000_000,
            center_frequency_hz=745_000_000,
            span_hz=10_000_000,
            rbw_estimate_hz=9765.625,
            sample_rate_hz=10_000_000,
            bins=1024,
            reference_level_dbm=10,
            occupancy_threshold_db=6,
            capture_seconds=0.25,
            window="hann",
        ),
        range_assessment=RangeAssessment(
            method="median_noise_floor_plus_threshold",
            threshold_offset_db=6,
            noise_floor_db_per_hz=-50,
            threshold_db_per_hz=-44,
            occupied_bins=128,
            occupancy_percent=12.5,
            occupied_bandwidth_hz=1_250_000,
            mean_excess_db=2,
            peak_to_floor_db=9,
            label="moderate",
        ),
    )
