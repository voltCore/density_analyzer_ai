import asyncio
import json

import numpy as np

from spectrana_density.config import Settings
from spectrana_density.schemas import DensityRequest
from spectrana_density.sources.aaronia import (
    AaroniaIQSource,
    AaroniaStreamParser,
    iter_frames_from_bytes,
)


def test_aaronia_stream_parser_decodes_raw16_iq_frame() -> None:
    header = {
        "samples": 3,
        "sampleSize": 2,
        "scale": 10,
        "size": 12,
        "startFrequency": 100_000_000,
        "endFrequency": 101_000_000,
        "unit": "volt",
    }
    values = np.array([10, 20, -30, 40, 50, -60], dtype="<i2")
    data = json.dumps(header).encode("utf-8") + b"\n\x1e" + values.tobytes() + b"\x1e"

    frames = list(iter_frames_from_bytes(data, sample_format="int16"))

    assert len(frames) == 1
    np.testing.assert_allclose(frames[0].samples, np.array([1 + 2j, -3 + 4j, 5 - 6j]))
    assert frames[0].frequency_from_hz == 100_000_000
    assert frames[0].frequency_to_hz == 101_000_000
    assert frames[0].unit == "volt"


def test_aaronia_stream_parser_waits_for_full_payload() -> None:
    header = {"samples": 2, "sampleSize": 2, "scale": 1}
    values = np.array([1.0, -1.0, 2.0, -2.0], dtype="<f4")
    data = json.dumps(header).encode("utf-8") + b"\n\x1e" + values.tobytes()
    split_at = len(data) - 3
    parser = AaroniaStreamParser(sample_format="raw32")

    assert parser.feed(data[:split_at]) == []
    frames = parser.feed(data[split_at:])

    assert len(frames) == 1
    np.testing.assert_allclose(frames[0].samples, np.array([1 - 1j, 2 - 2j]))


def test_aaronia_capture_does_not_stop_at_max_capture_samples(monkeypatch) -> None:
    bins = 1024
    chunks = [_raw32_frame(np.ones(bins, dtype=np.complex64) * index) for index in range(1, 4)]

    class FakeStreamResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self):
            for chunk in chunks:
                yield chunk

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def stream(self, _method: str, _url: str) -> FakeStreamResponse:
            return FakeStreamResponse()

    monkeypatch.setattr("spectrana_density.sources.aaronia.httpx.AsyncClient", FakeAsyncClient)

    source = AaroniaIQSource(
        Settings(
            aaronia_stream_url="http://example.test/stream?format=raw32",
            max_capture_samples=bins,
        )
    )
    request = DensityRequest(
        frequency_from_hz=100_000_000,
        frequency_to_hz=101_000_000,
        bins=bins,
        capture_seconds=30.0,
        apply_to_device=False,
    )

    capture = asyncio.run(source._read_capture(request))

    assert capture.packet_count == 3
    assert capture.sample_count == bins * 3


def test_aaronia_capture_crops_wider_stream_to_requested_range(monkeypatch) -> None:
    chunks = [
        _raw32_frame(
            np.ones(32, dtype=np.complex64),
            start_frequency_hz=90_000_000,
            end_frequency_hz=130_000_000,
        )
    ]

    class FakeStreamResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self):
            for chunk in chunks:
                yield chunk

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def stream(self, _method: str, _url: str) -> FakeStreamResponse:
            return FakeStreamResponse()

    monkeypatch.setattr("spectrana_density.sources.aaronia.httpx.AsyncClient", FakeAsyncClient)

    source = AaroniaIQSource(
        Settings(
            aaronia_stream_url="http://example.test/stream?format=raw32",
        )
    )
    request = DensityRequest(
        frequency_from_hz=100_000_000,
        frequency_to_hz=120_000_000,
        bins=16,
        capture_seconds=30.0,
        apply_to_device=False,
    )

    capture = asyncio.run(source.capture(request))

    assert capture.frequency_from_hz == 100_000_000
    assert capture.frequency_to_hz == 120_000_000
    assert capture.density is not None
    assert capture.density.frequencies_hz.size == 8
    assert capture.metadata["actual_stream_frequency_from_hz"] == 90_000_000
    assert capture.metadata["actual_stream_frequency_to_hz"] == 130_000_000
    assert capture.metadata["cropped_to_requested_range"] is True


def _raw32_frame(
    samples: np.ndarray,
    *,
    start_frequency_hz: float | None = None,
    end_frequency_hz: float | None = None,
) -> bytes:
    values = np.empty(samples.size * 2, dtype="<f4")
    values[0::2] = samples.real
    values[1::2] = samples.imag
    header: dict[str, int | float] = {
        "samples": samples.size,
        "sampleSize": 2,
        "sampleDepth": 1,
        "scale": 1,
    }
    if start_frequency_hz is not None:
        header["startFrequency"] = start_frequency_hz
    if end_frequency_hz is not None:
        header["endFrequency"] = end_frequency_hz
    return json.dumps(header).encode("utf-8") + b"\n\x1e" + values.tobytes() + b"\x1e"
