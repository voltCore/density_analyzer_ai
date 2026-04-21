import asyncio

import httpx
import pytest

from spectrana_density.ai_agent import (
    AIComparisonUnavailableError,
    _extract_error_message,
    build_comparison_context,
    explain_signal_comparison,
)
from spectrana_density.config import Settings
from spectrana_density.schemas import (
    AIComparisonRequest,
    BinDensity,
    CaptureSettings,
    DensityResponse,
    DensitySummary,
    RangeAssessment,
)


def test_build_comparison_context_identifies_denser_comparison() -> None:
    payload = AIComparisonRequest(
        baseline_name="Signal A",
        comparison_name="Signal B",
        baseline=_density_response(occupancy_percent=12.5, occupied_bins=128),
        comparison=_density_response(
            occupancy_percent=20.0,
            occupied_bins=205,
            mean_density_db_per_hz=-41.0,
        ),
    )

    context = build_comparison_context(payload)

    assert context["response_language"] == "en"
    assert context["comparison_quality"] == "direct"
    assert context["local_assessment"]["winner"] == "comparison"
    assert context["local_assessment"]["winner_name"] == "Signal B"
    assert context["local_assessment"]["primary_metric"] == "occupancy_percent"
    assert "is denser" in context["local_assessment"]["numeric_basis"]
    assert context["deltas_comparison_minus_baseline"]["occupancy_percent_points"] == 7.5


def test_build_comparison_context_marks_caution_for_nonmatching_capture() -> None:
    payload = AIComparisonRequest(
        baseline_name="Signal A",
        comparison_name="Signal B",
        baseline=_density_response(occupancy_percent=12.5, occupied_bins=128),
        comparison=_density_response(
            frequency_to_hz=760_000_000,
            bins_count=2048,
            occupancy_percent=14.0,
            occupied_bins=286,
            include_bins=False,
        ),
    )

    context = build_comparison_context(payload)

    assert context["comparison_quality"] == "caution"
    assert any("Frequency ranges differ" in caveat for caveat in context["caveats"])
    assert any("FFT bin counts differ" in caveat for caveat in context["caveats"])
    assert any("no bin-level rows" in caveat for caveat in context["caveats"])


def test_build_comparison_context_uses_ukrainian_when_requested() -> None:
    payload = AIComparisonRequest(
        baseline_name="Signal A",
        comparison_name="Signal B",
        response_language="uk",
        baseline=_density_response(occupancy_percent=12.5, occupied_bins=128),
        comparison=_density_response(
            frequency_to_hz=760_000_000,
            bins_count=2048,
            occupancy_percent=20.0,
            occupied_bins=410,
            include_bins=False,
        ),
    )

    context = build_comparison_context(payload)

    assert context["response_language"] == "uk"
    assert "щільніший" in context["local_assessment"]["numeric_basis"]
    assert any("Діапазони частот різні" in caveat for caveat in context["caveats"])
    assert any("Кількість FFT bins різна" in caveat for caveat in context["caveats"])
    assert any("немає bin-level rows" in caveat for caveat in context["caveats"])


def test_build_comparison_context_separates_coverage_and_energy_winners() -> None:
    payload = AIComparisonRequest(
        baseline_name="Signal A",
        comparison_name="Signal B",
        response_language="uk",
        baseline=_density_response(
            occupancy_percent=48.34,
            occupied_bins=495,
            mean_density_db_per_hz=-47.093,
            peak_density_db_per_hz=-43.107,
            integrated_power_db=34.754,
        ),
        comparison=_density_response(
            occupancy_percent=47.339,
            occupied_bins=485,
            mean_density_db_per_hz=-43.69,
            peak_density_db_per_hz=-29.213,
            integrated_power_db=38.278,
        ),
    )

    context = build_comparison_context(payload)

    assert context["coverage_winner"]["winner"] == "signal_1"
    assert context["energy_winner"]["winner"] == "signal_2"
    assert context["signal_1_role"] == "baseline"
    assert context["signal_2_role"] == "comparison"
    assert "частотне покриття" in context["answer_style"]


def test_explain_signal_comparison_requires_api_key() -> None:
    payload = AIComparisonRequest(
        baseline_name="Signal A",
        comparison_name="Signal B",
        baseline=_density_response(occupancy_percent=12.5, occupied_bins=128),
        comparison=_density_response(occupancy_percent=20.0, occupied_bins=205),
    )

    with pytest.raises(AIComparisonUnavailableError, match="OPENAI_API_KEY"):
        asyncio.run(explain_signal_comparison(payload, Settings(ai_api_key="")))


def test_extract_error_message_reads_openai_error_payload() -> None:
    response = httpx.Response(
        400,
        json={
            "error": {
                "message": "Unsupported value: temperature is not supported.",
                "type": "invalid_request_error",
            }
        },
    )

    assert _extract_error_message(response) == "Unsupported value: temperature is not supported."


def _density_response(
    *,
    frequency_from_hz: float = 740_000_000,
    frequency_to_hz: float = 750_000_000,
    bins_count: int = 1024,
    occupancy_percent: float,
    occupied_bins: int,
    mean_density_db_per_hz: float = -44.5,
    peak_density_db_per_hz: float = -41.0,
    integrated_power_db: float = 16.2,
    include_bins: bool = True,
) -> DensityResponse:
    span_hz = frequency_to_hz - frequency_from_hz
    bin_width_hz = span_hz / bins_count
    return DensityResponse(
        source="aaronia",
        configured_device=True,
        summary=DensitySummary(
            frequency_from_hz=frequency_from_hz,
            frequency_to_hz=frequency_to_hz,
            center_frequency_hz=(frequency_from_hz + frequency_to_hz) / 2,
            span_hz=span_hz,
            iq_rate_hz=span_hz,
            sample_rate_hz=span_hz,
            sample_count=16_384,
            bin_count=bins_count,
            bin_width_hz=bin_width_hz,
            averaged_segments=16,
            density_unit="V^2/Hz",
            power_unit="V^2",
            mean_density_linear=1.0,
            mean_density_db_per_hz=mean_density_db_per_hz,
            peak_density_linear=2.0,
            peak_density_db_per_hz=peak_density_db_per_hz,
            peak_frequency_hz=(frequency_from_hz + frequency_to_hz) / 2,
            integrated_power_linear=3.0,
            integrated_power_db=integrated_power_db,
        ),
        capture_settings=CaptureSettings(
            frequency_from_hz=frequency_from_hz,
            frequency_to_hz=frequency_to_hz,
            center_frequency_hz=(frequency_from_hz + frequency_to_hz) / 2,
            span_hz=span_hz,
            iq_rate_hz=span_hz,
            rbw_estimate_hz=bin_width_hz,
            sample_rate_hz=span_hz,
            bins=bins_count,
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
            occupied_bins=occupied_bins,
            occupancy_percent=occupancy_percent,
            occupied_bandwidth_hz=occupied_bins * bin_width_hz,
            mean_excess_db=2,
            peak_to_floor_db=9,
            label="moderate",
        ),
        bins=_bins() if include_bins else [],
    )


def _bins() -> list[BinDensity]:
    return [
        BinDensity(
            index=0,
            frequency_hz=740_000_000,
            density_linear=1.0,
            density_db_per_hz=-44.0,
            power_linear=1.0,
            power_db=-20.0,
        ),
        BinDensity(
            index=1,
            frequency_hz=740_010_000,
            density_linear=2.0,
            density_db_per_hz=-40.0,
            power_linear=2.0,
            power_db=-18.0,
        ),
    ]
