from spectrana_density.schemas import (
    BinDensity,
    CaptureSettings,
    DensityResponse,
    DensitySummary,
    JammerAnalysisRequest,
    RangeAssessment,
)
from spectrana_density.signal.jammer import analyze_jammer


def test_analyze_jammer_counts_bins_raised_against_clean_baseline() -> None:
    baseline = _density_response([-120.0, -121.0, -119.0, -122.0])
    jammer = _density_response([-112.0, -113.0, -111.0, -114.0])

    analysis = analyze_jammer(
        JammerAnalysisRequest(
            baseline_name="clean",
            jammer_name="jammer on",
            threshold_db=6,
            baseline=baseline,
            jammer=jammer,
        )
    )

    assert analysis.analysis_quality == "bin_level"
    assert analysis.raised_bins == 4
    assert analysis.raised_percent == 100.0
    assert analysis.raised_bandwidth_hz == 4_000.0
    assert analysis.mean_delta_db == 8.0
    assert analysis.noise_floor_delta_db == 8.0
    assert analysis.label == "broadband"
    assert analysis.top_raised_bins[0].delta_db == 8.0


def test_analyze_jammer_warns_when_bins_are_missing() -> None:
    baseline = _density_response([-120.0, -121.0], include_bins=False)
    jammer = _density_response([-112.0, -113.0], include_bins=False)

    analysis = analyze_jammer(
        JammerAnalysisRequest(
            response_language="uk",
            threshold_db=6,
            baseline=baseline,
            jammer=jammer,
        )
    )

    assert analysis.analysis_quality == "summary_only"
    assert analysis.compared_bins == 0
    assert analysis.raised_percent == 0.0
    assert any("немає рядків" in warning for warning in analysis.warnings)


def _density_response(
    density_db: list[float],
    *,
    include_bins: bool = True,
) -> DensityResponse:
    frequency_from_hz = 100_000_000.0
    bin_width_hz = 1_000.0
    frequency_to_hz = frequency_from_hz + len(density_db) * bin_width_hz
    mean_density_db = sum(density_db) / len(density_db)
    peak_density_db = max(density_db)
    return DensityResponse(
        source="aaronia",
        configured_device=True,
        summary=DensitySummary(
            frequency_from_hz=frequency_from_hz,
            frequency_to_hz=frequency_to_hz,
            center_frequency_hz=(frequency_from_hz + frequency_to_hz) / 2,
            span_hz=frequency_to_hz - frequency_from_hz,
            sample_rate_hz=frequency_to_hz - frequency_from_hz,
            sample_count=4096,
            bin_count=len(density_db),
            bin_width_hz=bin_width_hz,
            averaged_segments=1,
            density_unit="unit^2/Hz",
            power_unit="unit^2",
            mean_density_linear=1.0,
            mean_density_db_per_hz=mean_density_db,
            peak_density_linear=1.0,
            peak_density_db_per_hz=peak_density_db,
            peak_frequency_hz=frequency_from_hz,
            integrated_power_linear=1.0,
            integrated_power_db=mean_density_db + 40,
        ),
        capture_settings=CaptureSettings(
            frequency_from_hz=frequency_from_hz,
            frequency_to_hz=frequency_to_hz,
            center_frequency_hz=(frequency_from_hz + frequency_to_hz) / 2,
            span_hz=frequency_to_hz - frequency_from_hz,
            rbw_estimate_hz=bin_width_hz,
            sample_rate_hz=frequency_to_hz - frequency_from_hz,
            bins=len(density_db),
            reference_level_dbm=None,
            occupancy_threshold_db=6,
            capture_seconds=0.25,
            window="hann",
        ),
        range_assessment=RangeAssessment(
            method="test",
            threshold_offset_db=6,
            noise_floor_db_per_hz=mean_density_db,
            threshold_db_per_hz=mean_density_db + 6,
            occupied_bins=0,
            occupancy_percent=0,
            occupied_bandwidth_hz=0,
            mean_excess_db=0,
            peak_to_floor_db=peak_density_db - mean_density_db,
            label="quiet",
        ),
        bins=[
            BinDensity(
                index=index,
                frequency_hz=frequency_from_hz + index * bin_width_hz,
                density_linear=1.0,
                density_db_per_hz=value,
                power_linear=1.0,
                power_db=value + 10,
            )
            for index, value in enumerate(density_db)
        ]
        if include_bins
        else [],
    )
