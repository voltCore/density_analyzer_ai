import numpy as np

from spectrana_density.signal.density import (
    StreamingDensityAccumulator,
    assess_range_density,
    compute_density,
)


def test_compute_density_finds_complex_tone_frequency() -> None:
    frequency_from_hz = 100_000_000.0
    frequency_to_hz = 101_000_000.0
    bins = 1024
    sample_rate_hz = frequency_to_hz - frequency_from_hz
    center_hz = (frequency_from_hz + frequency_to_hz) / 2
    tone_hz = 100_750_000.0
    offset_hz = tone_hz - center_hz
    sample_count = bins * 16
    t = np.arange(sample_count, dtype=np.float64) / sample_rate_hz
    samples = np.exp(2j * np.pi * offset_hz * t)

    result = compute_density(
        samples,
        frequency_from_hz=frequency_from_hz,
        frequency_to_hz=frequency_to_hz,
        bins=bins,
    )

    assert abs(result.peak_frequency_hz - tone_hz) <= result.bin_width_hz
    assert result.integrated_power_linear > 0
    assert result.averaged_segments == 16


def test_assess_range_density_counts_bins_above_noise_floor_threshold() -> None:
    density_db = np.array([-100.0, -99.0, -101.0, -75.0, -76.0, -98.0], dtype=np.float64)

    assessment = assess_range_density(
        density_db,
        bin_width_hz=1_000.0,
        threshold_offset_db=6.0,
    )

    assert assessment.occupied_bins == 2
    assert assessment.occupancy_percent == 2 / 6 * 100
    assert assessment.occupied_bandwidth_hz == 2_000.0
    assert assessment.label == "moderate"


def test_streaming_density_matches_batch_density() -> None:
    frequency_from_hz = 100_000_000.0
    frequency_to_hz = 101_000_000.0
    bins = 64
    rng = np.random.default_rng(7)
    samples = (rng.standard_normal(bins * 5 + 17) + 1j * rng.standard_normal(bins * 5 + 17)).astype(
        np.complex128
    )

    batch = compute_density(
        samples,
        frequency_from_hz=frequency_from_hz,
        frequency_to_hz=frequency_to_hz,
        bins=bins,
    )
    accumulator = StreamingDensityAccumulator(
        frequency_from_hz=frequency_from_hz,
        frequency_to_hz=frequency_to_hz,
        bins=bins,
    )

    accumulator.add_samples(samples[:31])
    accumulator.add_samples(samples[31:203])
    accumulator.add_samples(samples[203:])
    streamed = accumulator.finish()

    assert accumulator.sample_count == samples.size
    assert streamed.averaged_segments == batch.averaged_segments
    np.testing.assert_allclose(streamed.density_linear, batch.density_linear)
    np.testing.assert_allclose(streamed.power_linear, batch.power_linear)
