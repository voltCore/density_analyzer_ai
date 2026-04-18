from dataclasses import dataclass
from math import log10
from typing import Literal

import numpy as np
from numpy.typing import NDArray

EPSILON = 1e-30


@dataclass(frozen=True)
class DensityComputation:
    frequencies_hz: NDArray[np.float64]
    density_linear: NDArray[np.float64]
    density_db_per_hz: NDArray[np.float64]
    power_linear: NDArray[np.float64]
    power_db: NDArray[np.float64]
    bin_width_hz: float
    averaged_segments: int
    mean_density_linear: float
    mean_density_db_per_hz: float
    peak_density_linear: float
    peak_density_db_per_hz: float
    peak_frequency_hz: float
    integrated_power_linear: float
    integrated_power_db: float


@dataclass(frozen=True)
class RangeDensityAssessment:
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


def compute_density(
    samples: NDArray[np.complexfloating],
    *,
    frequency_from_hz: float,
    frequency_to_hz: float,
    bins: int,
    window: Literal["hann", "rectangular"] = "hann",
) -> DensityComputation:
    """Estimate signal density as averaged complex-IQ power spectral density.

    The result uses linear unit^2/Hz and dB(unit^2/Hz). If the IQ source is voltage
    calibrated, this becomes V^2/Hz. Otherwise it is normalized sample units.
    """

    if frequency_to_hz <= frequency_from_hz:
        msg = "frequency_to_hz must be greater than frequency_from_hz"
        raise ValueError(msg)
    if bins < 16:
        msg = "bins must be at least 16"
        raise ValueError(msg)
    if samples.size == 0:
        msg = "at least one IQ sample is required"
        raise ValueError(msg)

    sample_rate_hz = frequency_to_hz - frequency_from_hz
    bin_width_hz = sample_rate_hz / bins
    prepared = _prepare_samples(samples.astype(np.complex128, copy=False), bins)
    segments = prepared.reshape((-1, bins))
    weights = _window(window, bins)
    window_power = float(np.sum(weights**2))

    weighted = segments * weights
    spectrum = np.fft.fftshift(np.fft.fft(weighted, n=bins, axis=1), axes=1)
    psd = np.mean(np.abs(spectrum) ** 2, axis=0) / (sample_rate_hz * window_power)
    psd = psd.astype(np.float64, copy=False)
    power = psd * bin_width_hz

    density_db = _to_db(psd)
    power_db = _to_db(power)
    frequencies = frequency_from_hz + (np.arange(bins, dtype=np.float64) + 0.5) * bin_width_hz

    peak_index = int(np.argmax(psd))
    mean_density = float(np.mean(psd))
    peak_density = float(psd[peak_index])
    integrated_power = float(np.sum(power))

    return DensityComputation(
        frequencies_hz=frequencies,
        density_linear=psd,
        density_db_per_hz=density_db,
        power_linear=power,
        power_db=power_db,
        bin_width_hz=bin_width_hz,
        averaged_segments=int(segments.shape[0]),
        mean_density_linear=mean_density,
        mean_density_db_per_hz=_scalar_to_db(mean_density),
        peak_density_linear=peak_density,
        peak_density_db_per_hz=_scalar_to_db(peak_density),
        peak_frequency_hz=float(frequencies[peak_index]),
        integrated_power_linear=integrated_power,
        integrated_power_db=_scalar_to_db(integrated_power),
    )


def assess_range_density(
    density_db_per_hz: NDArray[np.float64],
    *,
    bin_width_hz: float,
    threshold_offset_db: float = 6.0,
) -> RangeDensityAssessment:
    """Assess how much of the requested range is occupied by signal-like bins."""

    if density_db_per_hz.size == 0:
        msg = "at least one density bin is required"
        raise ValueError(msg)

    noise_floor = float(np.median(density_db_per_hz))
    threshold = noise_floor + threshold_offset_db
    occupied = density_db_per_hz >= threshold
    occupied_bins = int(np.count_nonzero(occupied))
    occupancy_percent = occupied_bins / int(density_db_per_hz.size) * 100
    occupied_bandwidth_hz = occupied_bins * bin_width_hz
    peak_to_floor_db = float(np.max(density_db_per_hz) - noise_floor)

    if occupied_bins:
        mean_excess_db = float(np.mean(density_db_per_hz[occupied] - threshold))
    else:
        mean_excess_db = 0.0

    return RangeDensityAssessment(
        method="median_noise_floor_plus_threshold",
        threshold_offset_db=threshold_offset_db,
        noise_floor_db_per_hz=noise_floor,
        threshold_db_per_hz=threshold,
        occupied_bins=occupied_bins,
        occupancy_percent=occupancy_percent,
        occupied_bandwidth_hz=occupied_bandwidth_hz,
        mean_excess_db=mean_excess_db,
        peak_to_floor_db=peak_to_floor_db,
        label=_occupancy_label(occupancy_percent, peak_to_floor_db, threshold_offset_db),
    )


def _prepare_samples(samples: NDArray[np.complex128], bins: int) -> NDArray[np.complex128]:
    if samples.size < bins:
        return np.pad(samples, (0, bins - samples.size))

    segment_count = samples.size // bins
    trimmed = samples[: segment_count * bins]
    return trimmed


def _window(window: Literal["hann", "rectangular"], bins: int) -> NDArray[np.float64]:
    match window:
        case "hann":
            return np.hanning(bins).astype(np.float64, copy=False)
        case "rectangular":
            return np.ones(bins, dtype=np.float64)


def _to_db(values: NDArray[np.float64]) -> NDArray[np.float64]:
    return 10 * np.log10(np.maximum(values, EPSILON))


def _scalar_to_db(value: float) -> float:
    return 10 * log10(max(value, EPSILON))


def _occupancy_label(
    occupancy_percent: float,
    peak_to_floor_db: float,
    threshold_offset_db: float,
) -> Literal["quiet", "sparse", "moderate", "dense"]:
    if peak_to_floor_db < threshold_offset_db:
        return "quiet"
    if occupancy_percent < 10:
        return "sparse"
    if occupancy_percent < 35:
        return "moderate"
    return "dense"
