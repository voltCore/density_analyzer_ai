# ruff: noqa: RUF001
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from spectrana_density.schemas import (
    ConductedJammerComparisonRequest,
    ConductedJammerComparisonResponse,
    ConductedJammerCoverageLabel,
    ConductedJammerMetrics,
    ConductedJammerTopBin,
    ConductedJammerWinner,
    DensityResponse,
)

EPSILON = 1e-30
INTEGRATED_POWER_SIGNIFICANCE_DB = 1.5
RAISED_PERCENT_SIGNIFICANCE_POINTS = 5.0
DELTA_SIGNIFICANCE_DB = 1.5


@dataclass(frozen=True)
class _BinSeries:
    frequencies_hz: NDArray[np.float64]
    density_linear: NDArray[np.float64]
    frequency_from_hz: float
    frequency_to_hz: float
    bin_width_hz: float


@dataclass(frozen=True)
class _ComparedGrid:
    frequencies_hz: NDArray[np.float64]
    baseline_linear: NDArray[np.float64]
    jammer_a_linear: NDArray[np.float64]
    jammer_b_linear: NDArray[np.float64]
    frequency_from_hz: float
    frequency_to_hz: float
    bin_width_hz: float


def compare_conducted_jammers(
    payload: ConductedJammerComparisonRequest,
) -> ConductedJammerComparisonResponse:
    warnings = _build_compatibility_warnings(payload)
    baseline_name = payload.baseline_name or "Baseline"
    jammer_a_name = payload.jammer_a_name or "Jammer A"
    jammer_b_name = payload.jammer_b_name or "Jammer B"

    baseline = _series_from_response(payload.baseline)
    jammer_a = _series_from_response(payload.jammer_a)
    jammer_b = _series_from_response(payload.jammer_b)

    if baseline is None or jammer_a is None or jammer_b is None:
        missing_bins = [
            name
            for name, series in (
                (baseline_name, baseline),
                (jammer_a_name, jammer_a),
                (jammer_b_name, jammer_b),
            )
            if series is None
        ]
        warnings.append(
            "Missing or invalid bin-level density rows for: " + ", ".join(missing_bins) + "."
        )
        return _incompatible_response(
            payload,
            warnings=warnings,
            baseline_name=baseline_name,
            jammer_a_name=jammer_a_name,
            jammer_b_name=jammer_b_name,
            numeric_basis="No compatible bin-level data was available for all three snapshots.",
        )

    grid = _build_compared_grid(payload, baseline, jammer_a, jammer_b, warnings)
    if grid is None:
        return _incompatible_response(
            payload,
            warnings=warnings,
            baseline_name=baseline_name,
            jammer_a_name=jammer_a_name,
            jammer_b_name=jammer_b_name,
            numeric_basis="No frequency overlap remained after target range clipping.",
        )

    jammer_a_metrics = _calculate_metrics(
        frequencies_hz=grid.frequencies_hz,
        baseline_linear=grid.baseline_linear,
        jammer_linear=grid.jammer_a_linear,
        bin_width_hz=grid.bin_width_hz,
        threshold_db=payload.threshold_db,
        attenuation_db=payload.attenuation_db,
        top_bins_limit=payload.top_bins_limit,
    )
    jammer_b_metrics = _calculate_metrics(
        frequencies_hz=grid.frequencies_hz,
        baseline_linear=grid.baseline_linear,
        jammer_linear=grid.jammer_b_linear,
        bin_width_hz=grid.bin_width_hz,
        threshold_db=payload.threshold_db,
        attenuation_db=payload.attenuation_db,
        top_bins_limit=payload.top_bins_limit,
    )
    winner, numeric_basis = _pick_winner(jammer_a_metrics, jammer_b_metrics)
    winner_name = _winner_name(winner, jammer_a_name, jammer_b_name)
    analysis_quality = "caution" if warnings else "direct"

    return ConductedJammerComparisonResponse(
        method="conducted_jammer_comparison_v1",
        threshold_db=payload.threshold_db,
        attenuation_db=payload.attenuation_db,
        analysis_quality=analysis_quality,
        warnings=warnings,
        baseline_name=baseline_name,
        jammer_a_name=jammer_a_name,
        jammer_b_name=jammer_b_name,
        compared_frequency_from_hz=grid.frequency_from_hz,
        compared_frequency_to_hz=grid.frequency_to_hz,
        bin_width_hz=grid.bin_width_hz,
        jammer_a=jammer_a_metrics,
        jammer_b=jammer_b_metrics,
        winner=winner,
        winner_name=winner_name,
        numeric_basis=numeric_basis,
        summary=_build_summary(
            payload,
            winner=winner,
            winner_name=winner_name,
            jammer_a_name=jammer_a_name,
            jammer_b_name=jammer_b_name,
            jammer_a=jammer_a_metrics,
            jammer_b=jammer_b_metrics,
            numeric_basis=numeric_basis,
        ),
    )


def _build_compatibility_warnings(payload: ConductedJammerComparisonRequest) -> list[str]:
    warnings: list[str] = []
    snapshots = [payload.baseline, payload.jammer_a, payload.jammer_b]

    if payload.attenuation_db == 0:
        warnings.append(
            "attenuation_db is 0 dB; corrected_integrated_power_db is not adjusted for "
            "the conducted measurement chain."
        )

    ranges = {
        (
            snapshot.summary.frequency_from_hz,
            snapshot.summary.frequency_to_hz,
        )
        for snapshot in snapshots
    }
    if len(ranges) > 1:
        warnings.append("Frequency ranges differ between the selected snapshots.")

    bin_counts = {snapshot.summary.bin_count for snapshot in snapshots}
    bin_counts.update(snapshot.capture_settings.bins for snapshot in snapshots)
    bin_counts.update(len(snapshot.bins) for snapshot in snapshots if snapshot.bins)
    if len(bin_counts) > 1:
        warnings.append("FFT bin counts differ between the selected snapshots.")

    windows = {snapshot.capture_settings.window for snapshot in snapshots}
    if len(windows) > 1:
        warnings.append("FFT window settings differ between the selected snapshots.")

    source_modes = {snapshot.source for snapshot in snapshots}
    if len(source_modes) > 1:
        warnings.append("IQ source modes differ between the selected snapshots.")

    metadata_values = [snapshot.metadata for snapshot in snapshots]
    if any(metadata != metadata_values[0] for metadata in metadata_values[1:]):
        warnings.append("Snapshot metadata differs between the selected snapshots.")

    return warnings


def _series_from_response(response: DensityResponse) -> _BinSeries | None:
    if not response.bins:
        return None

    sorted_bins = sorted(response.bins, key=lambda bin_row: bin_row.frequency_hz)
    frequencies = np.array([bin_row.frequency_hz for bin_row in sorted_bins], dtype=np.float64)
    density_linear = np.array([bin_row.density_linear for bin_row in sorted_bins], dtype=np.float64)
    density_db = np.array(
        [bin_row.density_db_per_hz for bin_row in sorted_bins],
        dtype=np.float64,
    )

    converted_from_db = np.power(10.0, density_db / 10.0)
    density_linear = np.where(
        np.isfinite(density_linear) & (density_linear > 0),
        density_linear,
        converted_from_db,
    )
    valid = np.isfinite(frequencies) & np.isfinite(density_linear) & (density_linear > 0)
    if not np.any(valid):
        return None

    frequencies = frequencies[valid]
    density_linear = density_linear[valid]
    unique_frequencies, unique_indices = np.unique(frequencies, return_index=True)
    density_linear = density_linear[unique_indices]

    return _BinSeries(
        frequencies_hz=unique_frequencies.astype(np.float64, copy=False),
        density_linear=density_linear.astype(np.float64, copy=False),
        frequency_from_hz=response.summary.frequency_from_hz,
        frequency_to_hz=response.summary.frequency_to_hz,
        bin_width_hz=response.summary.bin_width_hz,
    )


def _build_compared_grid(
    payload: ConductedJammerComparisonRequest,
    baseline: _BinSeries,
    jammer_a: _BinSeries,
    jammer_b: _BinSeries,
    warnings: list[str],
) -> _ComparedGrid | None:
    overlap_from_hz = max(
        baseline.frequency_from_hz,
        jammer_a.frequency_from_hz,
        jammer_b.frequency_from_hz,
    )
    overlap_to_hz = min(
        baseline.frequency_to_hz,
        jammer_a.frequency_to_hz,
        jammer_b.frequency_to_hz,
    )
    if overlap_to_hz <= overlap_from_hz:
        warnings.append("The selected snapshots do not have a frequency overlap.")
        return None

    smallest_span_hz = min(
        baseline.frequency_to_hz - baseline.frequency_from_hz,
        jammer_a.frequency_to_hz - jammer_a.frequency_from_hz,
        jammer_b.frequency_to_hz - jammer_b.frequency_from_hz,
    )
    if overlap_to_hz - overlap_from_hz < smallest_span_hz * 0.1:
        warnings.append("Frequency overlap is less than 10% of the smallest snapshot span.")

    target_from_hz = payload.target_frequency_from_hz or overlap_from_hz
    target_to_hz = payload.target_frequency_to_hz or overlap_to_hz
    if target_from_hz < overlap_from_hz or target_to_hz > overlap_to_hz:
        warnings.append(
            "Target frequency range extends outside the shared snapshot overlap and was clipped."
        )

    compared_from_hz = max(target_from_hz, overlap_from_hz)
    compared_to_hz = min(target_to_hz, overlap_to_hz)
    if compared_to_hz <= compared_from_hz:
        warnings.append("No bins remain inside the requested target frequency range.")
        return None

    base_mask = (baseline.frequencies_hz >= compared_from_hz) & (
        baseline.frequencies_hz <= compared_to_hz
    )
    if not np.any(base_mask):
        warnings.append("Baseline snapshot has no bins inside the compared frequency range.")
        return None

    frequencies = baseline.frequencies_hz[base_mask]
    baseline_linear = baseline.density_linear[base_mask]
    jammer_a_linear = _interpolate_linear_density(jammer_a, frequencies)
    jammer_b_linear = _interpolate_linear_density(jammer_b, frequencies)

    valid = (
        np.isfinite(baseline_linear)
        & (baseline_linear > 0)
        & np.isfinite(jammer_a_linear)
        & (jammer_a_linear > 0)
        & np.isfinite(jammer_b_linear)
        & (jammer_b_linear > 0)
    )
    if not np.any(valid):
        warnings.append("No comparable bin centers remain on the shared frequency grid.")
        return None
    if int(np.count_nonzero(valid)) != int(frequencies.size):
        warnings.append("Some edge bins were dropped because a jammer snapshot did not cover them.")

    frequencies = frequencies[valid]
    if frequencies.size < 3:
        warnings.append("Frequency overlap is too small for a stable comparison.")

    return _ComparedGrid(
        frequencies_hz=frequencies,
        baseline_linear=baseline_linear[valid],
        jammer_a_linear=jammer_a_linear[valid],
        jammer_b_linear=jammer_b_linear[valid],
        frequency_from_hz=compared_from_hz,
        frequency_to_hz=compared_to_hz,
        bin_width_hz=_grid_bin_width(frequencies, baseline.bin_width_hz),
    )


def _interpolate_linear_density(
    series: _BinSeries,
    frequencies_hz: NDArray[np.float64],
) -> NDArray[np.float64]:
    return np.interp(
        frequencies_hz,
        series.frequencies_hz,
        series.density_linear,
        left=np.nan,
        right=np.nan,
    ).astype(np.float64, copy=False)


def _grid_bin_width(frequencies_hz: NDArray[np.float64], fallback_bin_width_hz: float) -> float:
    if frequencies_hz.size < 2:
        return float(fallback_bin_width_hz)
    return float(np.median(np.diff(frequencies_hz)))


def _calculate_metrics(
    *,
    frequencies_hz: NDArray[np.float64],
    baseline_linear: NDArray[np.float64],
    jammer_linear: NDArray[np.float64],
    bin_width_hz: float,
    threshold_db: float,
    attenuation_db: float,
    top_bins_limit: int,
) -> ConductedJammerMetrics:
    baseline_db = _to_db_array(baseline_linear)
    jammer_db = _to_db_array(jammer_linear)
    delta_db = jammer_db - baseline_db
    raised = delta_db >= threshold_db
    compared_bins = int(delta_db.size)
    raised_bins = int(np.count_nonzero(raised))
    raised_percent = raised_bins / compared_bins * 100 if compared_bins else 0.0
    peak_delta_index = int(np.argmax(delta_db)) if compared_bins else 0

    baseline_integrated_power_db = _to_db_scalar(float(np.sum(baseline_linear * bin_width_hz)))
    measured_integrated_power_db = _to_db_scalar(float(np.sum(jammer_linear * bin_width_hz)))

    return ConductedJammerMetrics(
        compared_bins=compared_bins,
        raised_bins=raised_bins,
        raised_percent=raised_percent,
        raised_bandwidth_hz=raised_bins * bin_width_hz,
        mean_delta_db=float(np.mean(delta_db)) if compared_bins else 0.0,
        median_delta_db=float(np.median(delta_db)) if compared_bins else 0.0,
        p90_delta_db=float(np.percentile(delta_db, 90)) if compared_bins else 0.0,
        max_delta_db=float(np.max(delta_db)) if compared_bins else 0.0,
        min_delta_db=float(np.min(delta_db)) if compared_bins else 0.0,
        noise_floor_delta_db=float(np.median(jammer_db) - np.median(baseline_db))
        if compared_bins
        else 0.0,
        mean_density_delta_db=_to_db_scalar(float(np.mean(jammer_linear)))
        - _to_db_scalar(float(np.mean(baseline_linear)))
        if compared_bins
        else 0.0,
        peak_density_delta_db=float(np.max(jammer_db) - np.max(baseline_db))
        if compared_bins
        else 0.0,
        integrated_power_delta_db=measured_integrated_power_db - baseline_integrated_power_db,
        measured_integrated_power_db=measured_integrated_power_db,
        corrected_integrated_power_db=measured_integrated_power_db + attenuation_db,
        peak_delta_frequency_hz=float(frequencies_hz[peak_delta_index]) if compared_bins else None,
        top_raised_bins=_top_raised_bins(
            frequencies_hz=frequencies_hz,
            baseline_db=baseline_db,
            jammer_db=jammer_db,
            delta_db=delta_db,
            raised=raised,
            limit=top_bins_limit,
        ),
        label=_coverage_label(raised_percent, compared_bins),
    )


def _top_raised_bins(
    *,
    frequencies_hz: NDArray[np.float64],
    baseline_db: NDArray[np.float64],
    jammer_db: NDArray[np.float64],
    delta_db: NDArray[np.float64],
    raised: NDArray[np.bool_],
    limit: int,
) -> list[ConductedJammerTopBin]:
    if limit <= 0 or not np.any(raised):
        return []

    raised_indices = np.flatnonzero(raised)
    ordered_indices = raised_indices[np.argsort(delta_db[raised_indices])[::-1]][:limit]
    return [
        ConductedJammerTopBin(
            frequency_hz=float(frequencies_hz[index]),
            baseline_density_db_per_hz=float(baseline_db[index]),
            jammer_density_db_per_hz=float(jammer_db[index]),
            delta_db=float(delta_db[index]),
        )
        for index in ordered_indices
    ]


def _coverage_label(
    raised_percent: float,
    compared_bins: int,
) -> ConductedJammerCoverageLabel:
    if compared_bins == 0:
        return "unknown"
    if raised_percent == 0:
        return "none"
    if raised_percent < 10:
        return "narrow"
    if raised_percent < 35:
        return "partial"
    if raised_percent < 75:
        return "wide"
    return "broadband"


def _pick_winner(
    jammer_a: ConductedJammerMetrics,
    jammer_b: ConductedJammerMetrics,
) -> tuple[ConductedJammerWinner, str]:
    if jammer_a.compared_bins == 0 or jammer_b.compared_bins == 0:
        return "unclear", "No comparable bins were available for both jammers."

    checks = [
        (
            "integrated_power_delta_db",
            jammer_a.integrated_power_delta_db,
            jammer_b.integrated_power_delta_db,
            INTEGRATED_POWER_SIGNIFICANCE_DB,
            "dB",
        ),
        (
            "raised_percent",
            jammer_a.raised_percent,
            jammer_b.raised_percent,
            RAISED_PERCENT_SIGNIFICANCE_POINTS,
            "percentage points",
        ),
        (
            "mean_delta_db",
            jammer_a.mean_delta_db,
            jammer_b.mean_delta_db,
            DELTA_SIGNIFICANCE_DB,
            "dB",
        ),
        (
            "p90_delta_db",
            jammer_a.p90_delta_db,
            jammer_b.p90_delta_db,
            DELTA_SIGNIFICANCE_DB,
            "dB",
        ),
    ]

    for metric_name, value_a, value_b, minimum_difference, unit in checks:
        difference = value_a - value_b
        if abs(difference) >= minimum_difference:
            winner: ConductedJammerWinner = "jammer_a" if difference > 0 else "jammer_b"
            leading = value_a if difference > 0 else value_b
            trailing = value_b if difference > 0 else value_a
            return (
                winner,
                f"{metric_name}: {leading:.3f} vs {trailing:.3f}; "
                f"difference {abs(difference):.3f} {unit} meets "
                f"the {minimum_difference:.3f} {unit} threshold.",
            )

    return (
        "tie",
        "All priority metrics are below the minimum significant difference thresholds.",
    )


def _winner_name(winner: ConductedJammerWinner, jammer_a_name: str, jammer_b_name: str) -> str:
    if winner == "jammer_a":
        return jammer_a_name
    if winner == "jammer_b":
        return jammer_b_name
    if winner == "tie":
        return "Tie"
    return "Unclear"


def _build_summary(
    payload: ConductedJammerComparisonRequest,
    *,
    winner: ConductedJammerWinner,
    winner_name: str,
    jammer_a_name: str,
    jammer_b_name: str,
    jammer_a: ConductedJammerMetrics,
    jammer_b: ConductedJammerMetrics,
    numeric_basis: str,
) -> str:
    if payload.response_language == "uk":
        return _build_ukrainian_summary(
            threshold_db=payload.threshold_db,
            winner=winner,
            winner_name=winner_name,
            jammer_a_name=jammer_a_name,
            jammer_b_name=jammer_b_name,
            jammer_a=jammer_a,
            jammer_b=jammer_b,
            numeric_basis=numeric_basis,
        )
    return _build_english_summary(
        threshold_db=payload.threshold_db,
        winner=winner,
        winner_name=winner_name,
        jammer_a_name=jammer_a_name,
        jammer_b_name=jammer_b_name,
        jammer_a=jammer_a,
        jammer_b=jammer_b,
        numeric_basis=numeric_basis,
    )


def _build_ukrainian_summary(
    *,
    threshold_db: float,
    winner: ConductedJammerWinner,
    winner_name: str,
    jammer_a_name: str,
    jammer_b_name: str,
    jammer_a: ConductedJammerMetrics,
    jammer_b: ConductedJammerMetrics,
    numeric_basis: str,
) -> str:
    if winner == "unclear":
        return (
            "Дані несумісні для надійного conducted-порівняння. Перевірте warnings, "
            "наявність bin-level rows і частотний overlap між baseline, Jammer A та Jammer B."
        )
    if winner == "tie":
        return (
            f"За заданими порогами {jammer_a_name} і {jammer_b_name} не мають значущої "
            "різниці у conducted RF-впливі. Основні метрики не перевищили мінімальні "
            f"пороги різниці. Числова база: {numeric_basis} Висновок стосується тільки "
            "кабельного вимірювання через заданий attenuator chain і не враховує антени, "
            "поляризацію або дальність у просторі."
        )

    winner_metrics = jammer_a if winner == "jammer_a" else jammer_b
    loser_name = jammer_b_name if winner == "jammer_a" else jammer_a_name
    loser_metrics = jammer_b if winner == "jammer_a" else jammer_a
    return (
        f"{winner_name} має сильніший conducted RF-вплив у цільовій смузі. Він піднімає "
        f"{winner_metrics.raised_percent:.1f}% порівнюваного діапазону вище baseline "
        f"на щонайменше {threshold_db:.1f} dB, тоді як {loser_name} піднімає "
        f"{loser_metrics.raised_percent:.1f}%. Інтегральна потужність {winner_name} "
        "також вища за пріоритетною логікою порівняння. Висновок стосується тільки "
        "кабельного вимірювання через заданий attenuator chain і не враховує антени, "
        "поляризацію або дальність у просторі."
    )


def _build_english_summary(
    *,
    threshold_db: float,
    winner: ConductedJammerWinner,
    winner_name: str,
    jammer_a_name: str,
    jammer_b_name: str,
    jammer_a: ConductedJammerMetrics,
    jammer_b: ConductedJammerMetrics,
    numeric_basis: str,
) -> str:
    if winner == "unclear":
        return (
            "The snapshots are not compatible enough for a reliable conducted comparison. "
            "Check warnings, bin-level rows, and frequency overlap."
        )
    if winner == "tie":
        return (
            f"{jammer_a_name} and {jammer_b_name} are tied by the configured significance "
            f"thresholds. Numeric basis: {numeric_basis} This conclusion applies only to "
            "the conducted cable measurement through the configured attenuator chain."
        )

    winner_metrics = jammer_a if winner == "jammer_a" else jammer_b
    loser_name = jammer_b_name if winner == "jammer_a" else jammer_a_name
    loser_metrics = jammer_b if winner == "jammer_a" else jammer_a
    return (
        f"{winner_name} has the stronger conducted RF impact in the target band. It raises "
        f"{winner_metrics.raised_percent:.1f}% of compared bins above baseline by at least "
        f"{threshold_db:.1f} dB, while {loser_name} raises {loser_metrics.raised_percent:.1f}%. "
        "The conclusion applies only to the conducted cable measurement through the configured "
        "attenuator chain and does not evaluate antennas, polarization, or free-space range."
    )


def _incompatible_response(
    payload: ConductedJammerComparisonRequest,
    *,
    warnings: list[str],
    baseline_name: str,
    jammer_a_name: str,
    jammer_b_name: str,
    numeric_basis: str,
) -> ConductedJammerComparisonResponse:
    empty_metrics = _empty_metrics()
    return ConductedJammerComparisonResponse(
        method="conducted_jammer_comparison_v1",
        threshold_db=payload.threshold_db,
        attenuation_db=payload.attenuation_db,
        analysis_quality="incompatible",
        warnings=warnings,
        baseline_name=baseline_name,
        jammer_a_name=jammer_a_name,
        jammer_b_name=jammer_b_name,
        compared_frequency_from_hz=None,
        compared_frequency_to_hz=None,
        bin_width_hz=None,
        jammer_a=empty_metrics,
        jammer_b=empty_metrics,
        winner="unclear",
        winner_name="Unclear",
        numeric_basis=numeric_basis,
        summary=_build_summary(
            payload,
            winner="unclear",
            winner_name="Unclear",
            jammer_a_name=jammer_a_name,
            jammer_b_name=jammer_b_name,
            jammer_a=empty_metrics,
            jammer_b=empty_metrics,
            numeric_basis=numeric_basis,
        ),
    )


def _empty_metrics() -> ConductedJammerMetrics:
    return ConductedJammerMetrics(
        compared_bins=0,
        raised_bins=0,
        raised_percent=0.0,
        raised_bandwidth_hz=0.0,
        mean_delta_db=0.0,
        median_delta_db=0.0,
        p90_delta_db=0.0,
        max_delta_db=0.0,
        min_delta_db=0.0,
        noise_floor_delta_db=0.0,
        mean_density_delta_db=0.0,
        peak_density_delta_db=0.0,
        integrated_power_delta_db=0.0,
        measured_integrated_power_db=0.0,
        corrected_integrated_power_db=0.0,
        peak_delta_frequency_hz=None,
        top_raised_bins=[],
        label="unknown",
    )


def _to_db_array(values: NDArray[np.float64]) -> NDArray[np.float64]:
    return 10.0 * np.log10(np.maximum(values, EPSILON))


def _to_db_scalar(value: float) -> float:
    return float(10.0 * np.log10(max(value, EPSILON)))
