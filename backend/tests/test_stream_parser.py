import json

import numpy as np

from spectrana_density.sources.aaronia import AaroniaStreamParser, iter_frames_from_bytes


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
