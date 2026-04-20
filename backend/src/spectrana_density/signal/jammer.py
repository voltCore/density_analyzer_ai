from __future__ import annotations

# ruff: noqa: RUF001
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from spectrana_density.schemas import (
    DensityResponse,
    JammerAnalysisRequest,
    JammerAnalysisResponse,
    JammerFrequencyBin,
)

LanguageCode = Literal["en", "uk"]


def analyze_jammer(payload: JammerAnalysisRequest) -> JammerAnalysisResponse:
    """Compare a jammer measurement against a clean baseline measurement."""

    baseline_name = payload.baseline_name or _message(payload.response_language, "baseline_name")
    jammer_name = payload.jammer_name or _message(payload.response_language, "jammer_name")
    warnings = _capture_warnings(payload.baseline, payload.jammer, payload.response_language)
    summary_deltas = _summary_deltas(payload.baseline, payload.jammer)

    baseline_bins = payload.baseline.bins
    jammer_bins = payload.jammer.bins
    if not baseline_bins or not jammer_bins:
        warnings.append(_message(payload.response_language, "missing_bins"))
        return _summary_only_response(
            payload=payload,
            baseline_name=baseline_name,
            jammer_name=jammer_name,
            warnings=warnings,
            summary_deltas=summary_deltas,
        )

    aligned = _align_density_bins(payload.baseline, payload.jammer)
    if aligned is None:
        warnings.append(_message(payload.response_language, "no_overlap"))
        return _summary_only_response(
            payload=payload,
            baseline_name=baseline_name,
            jammer_name=jammer_name,
            warnings=warnings,
            summary_deltas=summary_deltas,
            quality="incompatible",
        )

    frequencies_hz, baseline_density_db, jammer_density_db, bin_width_hz = aligned
    delta_db = jammer_density_db - baseline_density_db
    raised = delta_db >= payload.threshold_db
    raised_bins = int(np.count_nonzero(raised))
    compared_bins = int(delta_db.size)
    raised_percent = raised_bins / compared_bins * 100 if compared_bins else 0.0
    raised_bandwidth_hz = raised_bins * bin_width_hz
    peak_delta_index = int(np.argmax(delta_db)) if compared_bins else 0
    top_bins = _top_raised_bins(
        frequencies_hz=frequencies_hz,
        baseline_density_db=baseline_density_db,
        jammer_density_db=jammer_density_db,
        delta_db=delta_db,
        raised=raised,
        limit=payload.top_bins_limit,
    )
    label = _label_jammer_coverage(raised_percent, summary_deltas["noise_floor_delta_db"])

    return JammerAnalysisResponse(
        method="baseline_psd_delta_threshold",
        threshold_db=payload.threshold_db,
        analysis_quality="bin_level",
        warnings=warnings,
        baseline_name=baseline_name,
        jammer_name=jammer_name,
        compared_bins=compared_bins,
        compared_frequency_from_hz=_rounded(float(frequencies_hz[0])) if compared_bins else None,
        compared_frequency_to_hz=_rounded(float(frequencies_hz[-1])) if compared_bins else None,
        bin_width_hz=_rounded(bin_width_hz),
        raised_bins=raised_bins,
        raised_percent=_rounded(raised_percent),
        raised_bandwidth_hz=_rounded(raised_bandwidth_hz),
        mean_delta_db=_rounded(float(np.mean(delta_db))),
        median_delta_db=_rounded(float(np.median(delta_db))),
        p90_delta_db=_rounded(float(np.percentile(delta_db, 90))),
        max_delta_db=_rounded(float(np.max(delta_db))),
        min_delta_db=_rounded(float(np.min(delta_db))),
        peak_delta_frequency_hz=_rounded(float(frequencies_hz[peak_delta_index])),
        top_raised_bins=top_bins,
        label=label,
        summary=_summary_text(
            language=payload.response_language,
            raised_percent=raised_percent,
            threshold_db=payload.threshold_db,
            noise_floor_delta_db=summary_deltas["noise_floor_delta_db"],
            mean_density_delta_db=summary_deltas["mean_density_delta_db"],
            integrated_power_delta_db=summary_deltas["integrated_power_delta_db"],
            label=label,
        ),
        **summary_deltas,
    )


def _align_density_bins(
    baseline: DensityResponse,
    jammer: DensityResponse,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], float] | None:
    baseline_frequencies = np.array([item.frequency_hz for item in baseline.bins], dtype=np.float64)
    baseline_density = np.array(
        [item.density_db_per_hz for item in baseline.bins], dtype=np.float64
    )
    jammer_frequencies = np.array([item.frequency_hz for item in jammer.bins], dtype=np.float64)
    jammer_density = np.array([item.density_db_per_hz for item in jammer.bins], dtype=np.float64)

    baseline_order = np.argsort(baseline_frequencies)
    jammer_order = np.argsort(jammer_frequencies)
    baseline_frequencies = baseline_frequencies[baseline_order]
    baseline_density = baseline_density[baseline_order]
    jammer_frequencies = jammer_frequencies[jammer_order]
    jammer_density = jammer_density[jammer_order]

    overlap_from = max(float(baseline_frequencies[0]), float(jammer_frequencies[0]))
    overlap_to = min(float(baseline_frequencies[-1]), float(jammer_frequencies[-1]))
    if overlap_to <= overlap_from:
        return None

    mask = (baseline_frequencies >= overlap_from) & (baseline_frequencies <= overlap_to)
    frequencies = baseline_frequencies[mask]
    if frequencies.size == 0:
        return None

    baseline_density = baseline_density[mask]
    interpolated_jammer_density = np.interp(frequencies, jammer_frequencies, jammer_density)
    bin_width_hz = _estimate_bin_width_hz(frequencies, baseline.summary.bin_width_hz)
    return frequencies, baseline_density, interpolated_jammer_density, bin_width_hz


def _top_raised_bins(
    *,
    frequencies_hz: NDArray[np.float64],
    baseline_density_db: NDArray[np.float64],
    jammer_density_db: NDArray[np.float64],
    delta_db: NDArray[np.float64],
    raised: NDArray[np.bool_],
    limit: int,
) -> list[JammerFrequencyBin]:
    candidate_indices = np.flatnonzero(raised)
    if candidate_indices.size == 0:
        candidate_indices = np.arange(delta_db.size)

    sorted_indices = candidate_indices[np.argsort(delta_db[candidate_indices])[::-1]][:limit]
    return [
        JammerFrequencyBin(
            index=int(index),
            frequency_hz=_rounded(float(frequencies_hz[index])),
            baseline_density_db_per_hz=_rounded(float(baseline_density_db[index])),
            jammer_density_db_per_hz=_rounded(float(jammer_density_db[index])),
            delta_db=_rounded(float(delta_db[index])),
        )
        for index in sorted_indices
    ]


def _summary_deltas(baseline: DensityResponse, jammer: DensityResponse) -> dict[str, float]:
    return {
        "noise_floor_delta_db": _rounded(
            jammer.range_assessment.noise_floor_db_per_hz
            - baseline.range_assessment.noise_floor_db_per_hz
        ),
        "mean_density_delta_db": _rounded(
            jammer.summary.mean_density_db_per_hz - baseline.summary.mean_density_db_per_hz
        ),
        "peak_density_delta_db": _rounded(
            jammer.summary.peak_density_db_per_hz - baseline.summary.peak_density_db_per_hz
        ),
        "integrated_power_delta_db": _rounded(
            jammer.summary.integrated_power_db - baseline.summary.integrated_power_db
        ),
    }


def _summary_only_response(
    *,
    payload: JammerAnalysisRequest,
    baseline_name: str,
    jammer_name: str,
    warnings: list[str],
    summary_deltas: dict[str, float],
    quality: Literal["summary_only", "incompatible"] = "summary_only",
) -> JammerAnalysisResponse:
    label = _label_jammer_coverage(0.0, summary_deltas["noise_floor_delta_db"])
    return JammerAnalysisResponse(
        method="baseline_psd_delta_threshold",
        threshold_db=payload.threshold_db,
        analysis_quality=quality,
        warnings=warnings,
        baseline_name=baseline_name,
        jammer_name=jammer_name,
        compared_bins=0,
        raised_bins=0,
        raised_percent=0.0,
        raised_bandwidth_hz=0.0,
        label=label,
        summary=_summary_text(
            language=payload.response_language,
            raised_percent=0.0,
            threshold_db=payload.threshold_db,
            noise_floor_delta_db=summary_deltas["noise_floor_delta_db"],
            mean_density_delta_db=summary_deltas["mean_density_delta_db"],
            integrated_power_delta_db=summary_deltas["integrated_power_delta_db"],
            label=label,
        ),
        **summary_deltas,
    )


def _capture_warnings(
    baseline: DensityResponse,
    jammer: DensityResponse,
    language: LanguageCode,
) -> list[str]:
    warnings: list[str] = []
    if not _same_number(
        baseline.capture_settings.frequency_from_hz,
        jammer.capture_settings.frequency_from_hz,
    ) or not _same_number(
        baseline.capture_settings.frequency_to_hz,
        jammer.capture_settings.frequency_to_hz,
    ):
        warnings.append(_message(language, "range_mismatch"))
    if baseline.capture_settings.bins != jammer.capture_settings.bins:
        warnings.append(_message(language, "bins_mismatch"))
    if baseline.capture_settings.window != jammer.capture_settings.window:
        warnings.append(_message(language, "window_mismatch"))
    return warnings


def _label_jammer_coverage(
    raised_percent: float,
    noise_floor_delta_db: float,
) -> Literal["none", "narrow", "partial", "wide", "broadband", "unknown"]:
    if raised_percent >= 70:
        return "broadband"
    if raised_percent >= 35:
        return "wide"
    if raised_percent >= 10:
        return "partial"
    if raised_percent > 0:
        return "narrow"
    if noise_floor_delta_db >= 6:
        return "wide"
    if noise_floor_delta_db >= 3:
        return "partial"
    return "none"


def _summary_text(
    *,
    language: LanguageCode,
    raised_percent: float,
    threshold_db: float,
    noise_floor_delta_db: float,
    mean_density_delta_db: float,
    integrated_power_delta_db: float,
    label: str,
) -> str:
    return _message(
        language,
        "summary",
        label=_message(language, f"label_{label}"),
        raised_percent=f"{raised_percent:.3f}",
        threshold_db=f"{threshold_db:g}",
        noise_floor_delta_db=f"{noise_floor_delta_db:g}",
        mean_density_delta_db=f"{mean_density_delta_db:g}",
        integrated_power_delta_db=f"{integrated_power_delta_db:g}",
    )


def _estimate_bin_width_hz(frequencies_hz: NDArray[np.float64], fallback: float) -> float:
    if frequencies_hz.size < 2:
        return float(fallback)
    return float(np.median(np.diff(frequencies_hz)))


def _same_number(left: float, right: float, tolerance: float = 1e-6) -> bool:
    return abs(left - right) <= tolerance


def _rounded(value: float, digits: int = 6) -> float:
    return round(value, digits)


def _message(language: LanguageCode, key: str, **values: object) -> str:
    messages = _UK_MESSAGES if language == "uk" else _EN_MESSAGES
    return messages[key].format(**values)


_EN_MESSAGES = {
    "baseline_name": "Clean baseline",
    "jammer_name": "Jammer measurement",
    "missing_bins": (
        "One of the snapshots has no bin-level rows. Enable bin return before saving "
        "snapshots to calculate jammer occupied bandwidth."
    ),
    "no_overlap": "The snapshots do not share an overlapping frequency range.",
    "range_mismatch": "Frequency ranges differ; only the overlapping range can be compared.",
    "bins_mismatch": "FFT bin counts differ; jammer PSD is interpolated onto the baseline grid.",
    "window_mismatch": "FFT windows differ; density deltas may be biased by leakage differences.",
    "label_none": "no clear jammer rise",
    "label_narrow": "narrowband jammer activity",
    "label_partial": "partial-band jammer activity",
    "label_wide": "wideband jammer activity",
    "label_broadband": "broadband jammer activity",
    "label_unknown": "unknown",
    "summary": (
        "{label}: {raised_percent}% of compared bins rose by at least {threshold_db} dB "
        "against the clean baseline. PSD noise floor delta is {noise_floor_delta_db} dB, "
        "mean density delta is {mean_density_delta_db} dB, integrated power delta is "
        "{integrated_power_delta_db} dB."
    ),
}


_UK_MESSAGES = {
    "baseline_name": "Чистий baseline",
    "jammer_name": "Вимір із джамером",
    "missing_bins": (
        "В одному зі знімків немає рядків по клітинках. Увімкніть повернення bins перед "
        "збереженням знімків, щоб рахувати зайняту смугу джамера."
    ),
    "no_overlap": "Знімки не мають спільного частотного діапазону.",
    "range_mismatch": "Діапазони частот різні; порівнюється тільки спільний діапазон.",
    "bins_mismatch": (
        "Кількість FFT-клітинок різна; PSD джамера інтерполюється на сітку baseline."
    ),
    "window_mismatch": "FFT-вікна різні; delta щільності може зміщуватись через leakage.",
    "label_none": "немає явного підняття від джамера",
    "label_narrow": "вузькосмугова активність джамера",
    "label_partial": "часткова активність джамера",
    "label_wide": "широкосмугова активність джамера",
    "label_broadband": "суцільна широкосмугова активність джамера",
    "label_unknown": "невідомо",
    "summary": (
        "{label}: {raised_percent}% порівнюваних клітинок піднялись мінімум на "
        "{threshold_db} dB відносно чистого baseline. Delta PSD рівня шуму: "
        "{noise_floor_delta_db} dB, delta середньої щільності: {mean_density_delta_db} dB, "
        "delta інтегральної потужності: {integrated_power_delta_db} dB."
    ),
}
