from math import log10
from typing import Literal

import pytest

from spectrana_density.schemas import (
    BinDensity,
    CaptureSettings,
    ConductedJammerComparisonRequest,
    DensityResponse,
    DensitySummary,
    RangeAssessment,
)
from spectrana_density.signal.conducted_jammer import compare_conducted_jammers


def test_conducted_comparison_selects_jammer_b_when_stronger() -> None:
    baseline = _density_response([-100.0] * 10)
    jammer_a = _density_response([-92.0] * 4 + [-100.0] * 6)
    jammer_b = _density_response([-90.0] * 8 + [-100.0] * 2)

    result = compare_conducted_jammers(
        ConductedJammerComparisonRequest(
            baseline_name="Baseline",
            jammer_a_name="Jammer A",
            jammer_b_name="Jammer B",
            threshold_db=6.0,
            attenuation_db=60.0,
            baseline=baseline,
            jammer_a=jammer_a,
            jammer_b=jammer_b,
        )
    )

    assert result.winner == "jammer_b"
    assert result.winner_name == "Jammer B"
    assert result.jammer_a.raised_percent == pytest.approx(40.0)
    assert result.jammer_b.raised_percent == pytest.approx(80.0)
    assert result.jammer_b.integrated_power_delta_db > result.jammer_a.integrated_power_delta_db


def test_conducted_comparison_selects_jammer_a_when_stronger() -> None:
    baseline = _density_response([-100.0] * 10)
    jammer_a = _density_response([-88.0] * 7 + [-100.0] * 3)
    jammer_b = _density_response([-92.0] * 3 + [-100.0] * 7)

    result = compare_conducted_jammers(
        ConductedJammerComparisonRequest(
            threshold_db=6.0,
            attenuation_db=60.0,
            baseline=baseline,
            jammer_a=jammer_a,
            jammer_b=jammer_b,
        )
    )

    assert result.winner == "jammer_a"
    assert result.jammer_a.integrated_power_delta_db > result.jammer_b.integrated_power_delta_db


def test_conducted_comparison_ties_when_differences_are_small() -> None:
    baseline = _density_response([-100.0] * 20)
    jammer_a = _density_response([-93.8] * 20)
    jammer_b = _density_response([-93.2] * 20)

    result = compare_conducted_jammers(
        ConductedJammerComparisonRequest(
            threshold_db=6.0,
            attenuation_db=60.0,
            baseline=baseline,
            jammer_a=jammer_a,
            jammer_b=jammer_b,
        )
    )

    assert result.winner == "tie"
    assert result.jammer_a.raised_percent == pytest.approx(100.0)
    assert result.jammer_b.raised_percent == pytest.approx(100.0)


def test_conducted_comparison_is_unclear_without_frequency_overlap() -> None:
    baseline = _density_response([-100.0] * 8, frequency_from_hz=100_000_000.0)
    jammer_a = _density_response([-90.0] * 8, frequency_from_hz=200_000_000.0)
    jammer_b = _density_response([-88.0] * 8, frequency_from_hz=300_000_000.0)

    result = compare_conducted_jammers(
        ConductedJammerComparisonRequest(
            threshold_db=6.0,
            attenuation_db=60.0,
            baseline=baseline,
            jammer_a=jammer_a,
            jammer_b=jammer_b,
        )
    )

    assert result.winner == "unclear"
    assert result.analysis_quality == "incompatible"
    assert result.jammer_a.compared_bins == 0
    assert any("frequency overlap" in warning.lower() for warning in result.warnings)


def test_conducted_comparison_clips_to_target_frequency_range() -> None:
    baseline = _density_response([-100.0] * 10, frequency_from_hz=100_000_000.0)
    jammer_a = _density_response([-90.0] * 10, frequency_from_hz=100_000_000.0)
    jammer_b = _density_response([-88.0] * 10, frequency_from_hz=100_000_000.0)

    result = compare_conducted_jammers(
        ConductedJammerComparisonRequest(
            threshold_db=6.0,
            attenuation_db=60.0,
            target_frequency_from_hz=120_000_000.0,
            target_frequency_to_hz=160_000_000.0,
            baseline=baseline,
            jammer_a=jammer_a,
            jammer_b=jammer_b,
        )
    )

    assert result.compared_frequency_from_hz == pytest.approx(120_000_000.0)
    assert result.compared_frequency_to_hz == pytest.approx(160_000_000.0)
    assert result.jammer_a.compared_bins == 4
    assert result.jammer_b.compared_bins == 4


def test_conducted_comparison_calculates_raised_percent() -> None:
    baseline = _density_response([-100.0] * 4)
    jammer_a = _density_response([-94.0, -94.1, -93.0, -100.0])
    jammer_b = _density_response([-94.0, -94.1, -93.0, -100.0])

    result = compare_conducted_jammers(
        ConductedJammerComparisonRequest(
            threshold_db=6.0,
            attenuation_db=60.0,
            baseline=baseline,
            jammer_a=jammer_a,
            jammer_b=jammer_b,
        )
    )

    assert result.jammer_a.raised_bins == 2
    assert result.jammer_a.raised_percent == pytest.approx(50.0)
    assert [bin_row.delta_db for bin_row in result.jammer_a.top_raised_bins] == pytest.approx(
        [7.0, 6.0]
    )


def test_conducted_comparison_applies_attenuation_to_corrected_integrated_power() -> None:
    baseline = _density_response([-100.0, -100.0])
    jammer_a = _density_response([-90.0, -90.0])
    jammer_b = _density_response([-90.0, -90.0])

    result = compare_conducted_jammers(
        ConductedJammerComparisonRequest(
            threshold_db=6.0,
            attenuation_db=60.0,
            baseline=baseline,
            jammer_a=jammer_a,
            jammer_b=jammer_b,
        )
    )

    expected_measured_db = 10.0 * log10(2 * (10.0**-9) * 10_000_000.0)
    assert result.jammer_a.measured_integrated_power_db == pytest.approx(expected_measured_db)
    assert result.jammer_a.corrected_integrated_power_db == pytest.approx(
        expected_measured_db + 60.0
    )


def test_conducted_comparison_returns_ukrainian_summary() -> None:
    baseline = _density_response([-100.0] * 10)
    jammer_a = _density_response([-92.0] * 4 + [-100.0] * 6)
    jammer_b = _density_response([-90.0] * 8 + [-100.0] * 2)

    result = compare_conducted_jammers(
        ConductedJammerComparisonRequest(
            response_language="uk",
            threshold_db=6.0,
            attenuation_db=60.0,
            baseline=baseline,
            jammer_a=jammer_a,
            jammer_b=jammer_b,
        )
    )

    assert result.summary
    assert "кабельного вимірювання" in result.summary


def _density_response(
    density_db_per_hz: list[float],
    *,
    frequency_from_hz: float = 2_400_000_000.0,
    bin_width_hz: float = 10_000_000.0,
    source: Literal["mock", "aaronia"] = "aaronia",
    window: Literal["hann", "rectangular"] = "hann",
) -> DensityResponse:
    bins_count = len(density_db_per_hz)
    frequency_to_hz = frequency_from_hz + bins_count * bin_width_hz
    density_linear = [10.0 ** (value / 10.0) for value in density_db_per_hz]
    power_linear = [value * bin_width_hz for value in density_linear]
    integrated_power_linear = sum(power_linear)
    peak_index = max(range(bins_count), key=lambda index: density_db_per_hz[index])
    mean_density_linear = sum(density_linear) / bins_count
    peak_density_linear = density_linear[peak_index]
    peak_frequency_hz = frequency_from_hz + (peak_index + 0.5) * bin_width_hz
    noise_floor_db = sorted(density_db_per_hz)[bins_count // 2]
    threshold_db = noise_floor_db + 6.0
    occupied_bins = sum(value >= threshold_db for value in density_db_per_hz)

    return DensityResponse(
        source=source,
        configured_device=True,
        summary=DensitySummary(
            frequency_from_hz=frequency_from_hz,
            frequency_to_hz=frequency_to_hz,
            center_frequency_hz=(frequency_from_hz + frequency_to_hz) / 2.0,
            span_hz=frequency_to_hz - frequency_from_hz,
            sample_rate_hz=frequency_to_hz - frequency_from_hz,
            sample_count=bins_count * 16,
            bin_count=bins_count,
            bin_width_hz=bin_width_hz,
            averaged_segments=16,
            density_unit="V^2/Hz",
            power_unit="V^2",
            mean_density_linear=mean_density_linear,
            mean_density_db_per_hz=10.0 * log10(mean_density_linear),
            peak_density_linear=peak_density_linear,
            peak_density_db_per_hz=density_db_per_hz[peak_index],
            peak_frequency_hz=peak_frequency_hz,
            integrated_power_linear=integrated_power_linear,
            integrated_power_db=10.0 * log10(integrated_power_linear),
        ),
        capture_settings=CaptureSettings(
            frequency_from_hz=frequency_from_hz,
            frequency_to_hz=frequency_to_hz,
            center_frequency_hz=(frequency_from_hz + frequency_to_hz) / 2.0,
            span_hz=frequency_to_hz - frequency_from_hz,
            rbw_estimate_hz=bin_width_hz,
            sample_rate_hz=frequency_to_hz - frequency_from_hz,
            bins=bins_count,
            reference_level_dbm=10.0,
            occupancy_threshold_db=6.0,
            capture_seconds=0.25,
            window=window,
        ),
        range_assessment=RangeAssessment(
            method="median_noise_floor_plus_threshold",
            threshold_offset_db=6.0,
            noise_floor_db_per_hz=noise_floor_db,
            threshold_db_per_hz=threshold_db,
            occupied_bins=occupied_bins,
            occupancy_percent=occupied_bins / bins_count * 100.0,
            occupied_bandwidth_hz=occupied_bins * bin_width_hz,
            mean_excess_db=0.0,
            peak_to_floor_db=max(density_db_per_hz) - noise_floor_db,
            label="moderate",
        ),
        bins=[
            BinDensity(
                index=index,
                frequency_hz=frequency_from_hz + (index + 0.5) * bin_width_hz,
                density_linear=density_linear[index],
                density_db_per_hz=density_db,
                power_linear=power_linear[index],
                power_db=10.0 * log10(power_linear[index]),
            )
            for index, density_db in enumerate(density_db_per_hz)
        ],
        metadata={"test": True},
    )
