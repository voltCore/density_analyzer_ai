import asyncio
import json

import numpy as np

from spectrana_density.config import Settings
from spectrana_density.schemas import DensityRequest, DeviceSetting
from spectrana_density.sources.aaronia import (
    AaroniaIQSource,
    AaroniaStreamParser,
    _stream_status,
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


def test_density_request_accepts_center_frequency_and_iq_rate() -> None:
    request = DensityRequest.model_validate(
        {
            "center_frequency_hz": 100_500_000,
            "iq_rate_hz": 1_000_000,
        }
    )

    assert request.frequency_from_hz == 100_000_000
    assert request.frequency_to_hz == 101_000_000
    assert request.span_hz == 1_000_000


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
    request = DensityRequest.model_validate(
        {
            "frequency_from_hz": 100_000_000,
            "frequency_to_hz": 101_000_000,
            "bins": bins,
            "capture_seconds": 30.0,
            "apply_to_device": False,
        }
    )

    capture = asyncio.run(source._read_capture(request))

    assert capture.packet_count == 3
    assert capture.sample_count == bins * 3


def test_aaronia_capture_uses_stream_iq_rate_when_range_is_not_reported(monkeypatch) -> None:
    chunks = [
        _raw32_frame(
            np.ones(16, dtype=np.complex64),
            center_frequency_hz=101_000_000,
            sample_frequency_hz=2_000_000,
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

    source = AaroniaIQSource(Settings(aaronia_stream_url="http://example.test/stream?format=raw32"))
    request = DensityRequest.model_validate(
        {
            "center_frequency_hz": 101_000_000,
            "iq_rate_hz": 1_000_000,
            "bins": 16,
            "capture_seconds": 30.0,
            "apply_to_device": False,
        }
    )

    capture = asyncio.run(source.capture(request))

    assert capture.frequency_from_hz == 100_000_000
    assert capture.frequency_to_hz == 102_000_000
    assert capture.sample_rate_hz == 2_000_000
    assert capture.metadata["actual_iq_rate_hz"] == 2_000_000


def test_stream_status_derives_iq_rate_options_from_decimation() -> None:
    status = _stream_status(
        {"sampleFrequency": 76_500_000},
        {
            "span": DeviceSetting(
                label="Span",
                value="1/2",
                raw_value=1,
                options=["Full", "1/2", "1/4"],
            )
        },
    )

    assert status.iq_rate_hz == 76_500_000
    assert status.iq_rate_options_hz == [153_000_000, 76_500_000, 38_250_000]


def _raw32_frame(
    samples: np.ndarray,
    *,
    center_frequency_hz: float | None = None,
    sample_frequency_hz: float | None = None,
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
    if center_frequency_hz is not None:
        header["frequencyCenter"] = center_frequency_hz
    if sample_frequency_hz is not None:
        header["sampleFrequency"] = sample_frequency_hz
    return json.dumps(header).encode("utf-8") + b"\n\x1e" + values.tobytes() + b"\x1e"
