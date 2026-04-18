import numpy as np

from spectrana_density.config import Settings
from spectrana_density.schemas import DensityRequest
from spectrana_density.sources.base import IQCapture


class MockIQSource:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def capture(self, request: DensityRequest) -> IQCapture:
        span_hz = request.span_hz
        sample_rate_hz = span_hz
        sample_count = min(
            self._settings.max_capture_samples,
            max(request.bins * 32, 8192),
        )
        rng = np.random.default_rng(42)
        t = np.arange(sample_count, dtype=np.float64) / sample_rate_hz
        center_hz = request.center_frequency_hz

        tone_a_hz = request.frequency_from_hz + span_hz * 0.33
        tone_b_hz = request.frequency_from_hz + span_hz * 0.72
        offset_a_hz = tone_a_hz - center_hz
        offset_b_hz = tone_b_hz - center_hz

        noise = 0.03 * (rng.standard_normal(sample_count) + 1j * rng.standard_normal(sample_count))
        tone_a = 0.35 * np.exp(2j * np.pi * offset_a_hz * t)
        tone_b = 0.12 * np.exp(2j * np.pi * offset_b_hz * t)
        samples = (noise + tone_a + tone_b).astype(np.complex128)

        return IQCapture(
            samples=samples,
            sample_rate_hz=sample_rate_hz,
            frequency_from_hz=request.frequency_from_hz,
            frequency_to_hz=request.frequency_to_hz,
            unit="normalized",
            packet_count=1,
            configured_device=False,
            metadata={
                "mock_tone_a_hz": float(tone_a_hz),
                "mock_tone_b_hz": float(tone_b_hz),
            },
        )
