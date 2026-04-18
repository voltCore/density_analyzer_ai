import json
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import numpy as np
from numpy.typing import NDArray

from spectrana_density.config import Settings
from spectrana_density.schemas import (
    DensityRequest,
    DeviceSetting,
    DeviceStatusResponse,
    DeviceStreamStatus,
)
from spectrana_density.signal.density import DensityComputation, StreamingDensityAccumulator
from spectrana_density.sources.base import IQCapture

FRAME_SEPARATOR = b"\x1e"


@dataclass(frozen=True)
class IQFrame:
    header: dict[str, Any]
    samples: NDArray[np.complexfloating]

    @property
    def frequency_from_hz(self) -> float | None:
        value = self.header.get("startFrequency") or self.header.get("frequencyStart")
        return float(value) if value is not None else None

    @property
    def frequency_to_hz(self) -> float | None:
        value = self.header.get("endFrequency") or self.header.get("frequencyStop")
        return float(value) if value is not None else None

    @property
    def unit(self) -> str:
        value = self.header.get("unit")
        return str(value) if value else "normalized"


@dataclass(frozen=True)
class AaroniaStreamCapture:
    density: DensityComputation
    sample_count: int
    packet_count: int
    first_header: dict[str, Any]
    frequency_from_hz: float
    frequency_to_hz: float
    unit: str
    elapsed_seconds: float


class AaroniaStreamParser:
    """Incremental parser for RTSA HTTP IQ frames.

    The stream is expected as compact JSON header, LF, binary I/Q payload, and an
    optional ASCII record separator before the next frame.
    """

    def __init__(self, sample_format: str = "raw32") -> None:
        self._buffer = bytearray()
        self._sample_format = sample_format

    def feed(self, chunk: bytes) -> list[IQFrame]:
        self._buffer.extend(chunk)
        frames: list[IQFrame] = []

        while True:
            frame = self._try_parse_one()
            if frame is None:
                break
            frames.append(frame)

        return frames

    def _try_parse_one(self) -> IQFrame | None:
        self._drop_separators()
        try:
            header_end = self._buffer.index(0x0A)
        except ValueError:
            return None

        header_bytes = bytes(self._buffer[:header_end]).strip()
        if not header_bytes:
            del self._buffer[: header_end + 1]
            return None

        try:
            header = json.loads(header_bytes.decode("utf-8"))
        except json.JSONDecodeError as exc:
            msg = "Could not decode Aaronia stream JSON header"
            raise ValueError(msg) from exc

        payload_start = header_end + 1
        if len(self._buffer) <= payload_start:
            return None
        if self._buffer[payload_start] == 0x1E:
            payload_start += 1

        payload_length = _payload_length_bytes(header, self._sample_format)
        frame_end = payload_start + payload_length
        if len(self._buffer) < frame_end:
            return None

        payload = bytes(self._buffer[payload_start:frame_end])
        del self._buffer[:frame_end]
        self._drop_separators()

        return IQFrame(
            header=header,
            samples=_decode_iq_payload(payload, header, self._sample_format),
        )

    def _drop_separators(self) -> None:
        while self._buffer and self._buffer[0] in {0x0A, 0x0D, 0x1E}:
            del self._buffer[0]


class AaroniaIQSource:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def capture(self, request: DensityRequest) -> IQCapture:
        configured_device = False
        if request.apply_to_device:
            await self._configure_device(request)
            configured_device = True

        stream_capture = await self._read_capture(request)
        first_header = stream_capture.first_header
        sample_rate_hz = stream_capture.frequency_to_hz - stream_capture.frequency_from_hz

        return IQCapture(
            samples=np.empty(0, dtype=np.complex128),
            sample_rate_hz=sample_rate_hz,
            frequency_from_hz=stream_capture.frequency_from_hz,
            frequency_to_hz=stream_capture.frequency_to_hz,
            unit=stream_capture.unit,
            packet_count=stream_capture.packet_count,
            configured_device=configured_device,
            sample_count=stream_capture.sample_count,
            density=stream_capture.density,
            metadata={
                "stream_url": self._settings.aaronia_stream_url,
                "control_url": self._settings.aaronia_control_url,
                "first_packet_num": first_header.get("num"),
                "first_packet_size": first_header.get("size"),
                "first_packet_sample_size": first_header.get("sampleSize"),
                "first_packet_samples": first_header.get("samples"),
                "stream_sample_count": stream_capture.sample_count,
                "capture_elapsed_seconds": stream_capture.elapsed_seconds,
                "density_mode": "streaming_fft_average",
            },
        )

    async def _configure_device(self, request: DensityRequest) -> None:
        payload: dict[str, str | int | float | bool] = {
            "type": "capture",
            "frequencyStart": request.frequency_from_hz,
            "frequencyEnd": request.frequency_to_hz,
            "frequencyCenter": request.center_frequency_hz,
            "frequencySpan": request.span_hz,
            "frequencyBins": request.bins,
        }
        if request.reference_level_dbm is not None:
            payload["referenceLevel"] = request.reference_level_dbm
        if self._settings.aaronia_receiver_name:
            payload["receiver"] = self._settings.aaronia_receiver_name

        timeout = httpx.Timeout(self._settings.request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.request(
                    self._settings.aaronia_control_method,
                    self._settings.aaronia_control_url,
                    json=payload,
                )
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                msg = (
                    "Timed out while connecting to Aaronia control endpoint "
                    f"{self._settings.aaronia_control_url}"
                )
                raise RuntimeError(msg) from exc
            except httpx.HTTPError as exc:
                msg = f"Aaronia control endpoint failed: {exc}"
                raise RuntimeError(msg) from exc

    async def _read_capture(self, request: DensityRequest) -> AaroniaStreamCapture:
        parser = AaroniaStreamParser(
            sample_format=_stream_format(self._settings.aaronia_stream_url),
        )
        first_header: dict[str, Any] | None = None
        frequency_from_hz = request.frequency_from_hz
        frequency_to_hz = request.frequency_to_hz
        unit = "normalized"
        accumulator: StreamingDensityAccumulator | None = None
        packet_count = 0
        sample_count = 0
        started_at = time.monotonic()
        deadline = started_at + request.capture_seconds
        timeout = httpx.Timeout(
            connect=self._settings.stream_connect_timeout_seconds,
            read=self._settings.stream_read_timeout_seconds,
            write=self._settings.request_timeout_seconds,
            pool=self._settings.request_timeout_seconds,
        )

        try:
            async with (
                httpx.AsyncClient(timeout=timeout) as client,
                client.stream("GET", self._settings.aaronia_stream_url) as response,
            ):
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    for frame in parser.feed(chunk):
                        if first_header is None:
                            first_header = frame.header
                            frequency_from_hz = frame.frequency_from_hz or request.frequency_from_hz
                            frequency_to_hz = frame.frequency_to_hz or request.frequency_to_hz
                            unit = frame.unit
                            accumulator = StreamingDensityAccumulator(
                                frequency_from_hz=frequency_from_hz,
                                frequency_to_hz=frequency_to_hz,
                                bins=request.bins,
                                window=request.window,
                            )

                        if accumulator is None:
                            msg = "Aaronia stream accumulator was not initialized"
                            raise RuntimeError(msg)

                        accumulator.add_samples(frame.samples)
                        packet_count += 1
                        sample_count += int(frame.samples.size)

                    if sample_count >= request.bins and time.monotonic() >= deadline:
                        break
        except httpx.TimeoutException as exc:
            msg = f"Timed out while reading Aaronia IQ stream {self._settings.aaronia_stream_url}"
            raise RuntimeError(msg) from exc
        except httpx.HTTPError as exc:
            msg = f"Aaronia IQ stream failed: {exc}"
            raise RuntimeError(msg) from exc

        if first_header is None or accumulator is None:
            msg = "Aaronia stream did not return any IQ frames"
            raise RuntimeError(msg)

        return AaroniaStreamCapture(
            density=accumulator.finish(),
            sample_count=sample_count,
            packet_count=packet_count,
            first_header=first_header,
            frequency_from_hz=frequency_from_hz,
            frequency_to_hz=frequency_to_hz,
            unit=unit,
            elapsed_seconds=time.monotonic() - started_at,
        )


async def read_aaronia_device_status(settings: Settings) -> DeviceStatusResponse:
    endpoints = {
        "info": _endpoint(settings.aaronia_stream_url, "/info"),
        "inputs": _endpoint(settings.aaronia_stream_url, "/inputs"),
        "remoteconfig": _endpoint(settings.aaronia_stream_url, "/remoteconfig"),
        "healthstatus": _endpoint(settings.aaronia_stream_url, "/healthstatus"),
        "stream": settings.aaronia_stream_url,
        "control": settings.aaronia_control_url,
    }
    timeout = httpx.Timeout(settings.request_timeout_seconds)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            info = await _get_json(client, endpoints["info"])
            inputs_data = await _get_json(client, endpoints["inputs"])
            remote_config = await _get_json(client, endpoints["remoteconfig"])
            health_status = await _get_json(client, endpoints["healthstatus"])
            stream_header = await _read_stream_header(client, settings.aaronia_stream_url)
    except httpx.HTTPError as exc:
        return DeviceStatusResponse(
            source="aaronia",
            reachable=False,
            endpoints=endpoints,
            error=str(exc),
        )
    except ValueError as exc:
        return DeviceStatusResponse(
            source="aaronia",
            reachable=False,
            endpoints=endpoints,
            error=str(exc),
        )

    settings_map = _extract_device_settings(remote_config)
    stream = _stream_status(stream_header, settings_map)
    return DeviceStatusResponse(
        source="aaronia",
        reachable=True,
        endpoints=endpoints,
        info=_simple_mapping(info),
        inputs=[str(item) for item in inputs_data.get("inputs", [])],
        health_state=_extract_health_state(health_status),
        stream=stream,
        settings=settings_map,
    )


def mock_device_status(settings: Settings) -> DeviceStatusResponse:
    span_hz = settings.default_frequency_to_hz - settings.default_frequency_from_hz
    return DeviceStatusResponse(
        source="mock",
        reachable=True,
        endpoints={},
        inputs=["mock"],
        health_state="running",
        stream=DeviceStreamStatus(
            payload="iq",
            unit="normalized",
            frequency_from_hz=settings.default_frequency_from_hz,
            frequency_to_hz=settings.default_frequency_to_hz,
            center_frequency_hz=(
                settings.default_frequency_from_hz + settings.default_frequency_to_hz
            )
            / 2,
            span_hz=span_hz,
            sample_frequency_hz=span_hz,
            rbw_from_fft_size_hz=span_hz / settings.default_bins,
        ),
        settings={
            "center_frequency_hz": DeviceSetting(
                label="Center Frequency",
                value=(settings.default_frequency_from_hz + settings.default_frequency_to_hz) / 2,
                unit="Hz",
            ),
            "span": DeviceSetting(label="Span", value=span_hz, unit="Hz"),
            "fft_size": DeviceSetting(label="FFT Size", value=settings.default_bins),
        },
    )


def _payload_length_bytes(header: dict[str, Any], sample_format: str) -> int:
    size = header.get("size")
    if size is not None and int(size) > 0:
        return int(size)

    samples = int(header.get("samples", 0))
    values_per_sample = int(header.get("sampleSize", 0))
    sample_depth = int(header.get("sampleDepth", 1))
    value_size_bytes = _value_size_bytes(sample_format)
    if samples <= 0 or values_per_sample <= 0 or sample_depth <= 0:
        msg = "Aaronia IQ header must contain positive samples, sampleSize and sampleDepth"
        raise ValueError(msg)

    return samples * values_per_sample * sample_depth * value_size_bytes


def _decode_iq_payload(
    payload: bytes,
    header: dict[str, Any],
    sample_format: str,
) -> NDArray[np.complexfloating]:
    scale = float(header.get("scale") or 1.0)

    raw_values = _decode_payload_values(payload, sample_format)
    if raw_values.size % 2 != 0:
        msg = "Aaronia IQ payload must contain interleaved I/Q values"
        raise ValueError(msg)

    scaled = raw_values.astype(np.float64, copy=False)
    if sample_format == "int16":
        scaled = scaled / scale
    i_values = scaled[0::2]
    q_values = scaled[1::2]
    return (i_values + 1j * q_values).astype(np.complex128, copy=False)


def _decode_payload_values(payload: bytes, sample_format: str) -> NDArray[np.floating | np.integer]:
    match sample_format:
        case "raw32":
            return np.frombuffer(payload, dtype="<f4")
        case "int16":
            return np.frombuffer(payload, dtype="<i2")
        case _:
            msg = f"Unsupported Aaronia IQ stream format={sample_format}"
            raise ValueError(msg)


def _value_size_bytes(sample_format: str) -> int:
    match sample_format:
        case "raw32":
            return 4
        case "int16":
            return 2
        case _:
            msg = f"Unsupported Aaronia IQ stream format={sample_format}"
            raise ValueError(msg)


def _stream_format(stream_url: str) -> str:
    parsed = urlparse(stream_url)
    query = parse_qs(parsed.query)
    return query.get("format", ["raw32"])[0]


def _endpoint(stream_url: str, path: str) -> str:
    parsed = urlparse(stream_url)
    return f"{parsed.scheme}://{parsed.netloc}{path}"


async def _get_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        msg = f"Endpoint {url} did not return a JSON object"
        raise ValueError(msg)
    return data


async def _read_stream_header(client: httpx.AsyncClient, stream_url: str) -> dict[str, Any]:
    buffer = bytearray()
    async with client.stream("GET", stream_url) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes(chunk_size=1024):
            buffer.extend(chunk)
            if 0x0A in buffer:
                header_end = buffer.index(0x0A)
                return json.loads(bytes(buffer[:header_end]).decode("utf-8"))
    msg = "Aaronia stream did not return a JSON header"
    raise ValueError(msg)


def _extract_device_settings(remote_config: Mapping[str, Any]) -> dict[str, DeviceSetting]:
    items = list(_walk_config(remote_config.get("config", remote_config)))
    wanted = {
        "center_frequency_hz": "centerfreq",
        "span": "decimation",
        "reference_level_dbm": "reflevel",
        "fft_size": "fftsize",
        "fft_size_mode": "fftsizemode",
        "fft_window": "fftwindow",
        "receiver_clock": "receiverclock",
        "frequency_range": "frequencyrange",
    }

    result: dict[str, DeviceSetting] = {}
    for output_name, remote_name in wanted.items():
        candidates = [item for item in items if item["name"] == remote_name]
        if not candidates:
            continue
        item = _prefer_spectran_item(candidates)
        result[output_name] = _device_setting(item)

    return result


def _walk_config(node: Any, path: str = "") -> Iterator[dict[str, Any]]:
    if not isinstance(node, dict):
        return

    name = str(node.get("name", ""))
    current_path = f"{path}/{name}" if name else path
    if "value" in node:
        yield {**node, "path": current_path}

    for item in node.get("items", []) or []:
        yield from _walk_config(item, current_path)


def _prefer_spectran_item(items: list[dict[str, Any]]) -> dict[str, Any]:
    for item in items:
        if "Block_Spectran" in str(item.get("path", "")):
            return item
    return items[0]


def _device_setting(item: Mapping[str, Any]) -> DeviceSetting:
    raw_value = item.get("value")
    value = _enum_label(item) if item.get("values") is not None else raw_value
    return DeviceSetting(
        label=str(item.get("label") or item.get("name") or "Setting"),
        value=value,
        raw_value=raw_value,
        unit=str(item["unit"]) if item.get("unit") is not None else None,
        path=str(item.get("path")) if item.get("path") is not None else None,
    )


def _enum_label(item: Mapping[str, Any]) -> str | int | float | bool | None:
    raw_value = item.get("value")
    values = item.get("values")
    if not isinstance(values, str):
        return raw_value
    options = [value.strip() for value in values.split(",")]
    if isinstance(raw_value, int) and 0 <= raw_value < len(options):
        return options[raw_value]
    return raw_value


def _extract_health_state(health_status: Mapping[str, Any]) -> str | None:
    for item in _walk_config(health_status):
        if item.get("name") != "state":
            continue
        label = _enum_label(item)
        return str(label) if label is not None else None
    return None


def _stream_status(
    stream_header: Mapping[str, Any],
    settings_map: Mapping[str, DeviceSetting],
) -> DeviceStreamStatus:
    frequency_from_hz = _float_or_none(stream_header.get("startFrequency"))
    frequency_to_hz = _float_or_none(stream_header.get("endFrequency"))
    span_hz = (
        frequency_to_hz - frequency_from_hz
        if frequency_from_hz is not None and frequency_to_hz is not None
        else None
    )
    fft_size_setting = settings_map.get("fft_size")
    fft_size = _float_or_none(fft_size_setting.raw_value) if fft_size_setting else None

    return DeviceStreamStatus(
        payload=_str_or_none(stream_header.get("payload")),
        unit=_str_or_none(stream_header.get("unit")),
        frequency_from_hz=frequency_from_hz,
        frequency_to_hz=frequency_to_hz,
        center_frequency_hz=(
            (frequency_from_hz + frequency_to_hz) / 2
            if frequency_from_hz is not None and frequency_to_hz is not None
            else None
        ),
        span_hz=span_hz,
        sample_frequency_hz=_float_or_none(stream_header.get("sampleFrequency")),
        samples_per_packet=_int_or_none(stream_header.get("samples")),
        sample_size=_int_or_none(stream_header.get("sampleSize")),
        sample_depth=_int_or_none(stream_header.get("sampleDepth")),
        scale=_float_or_none(stream_header.get("scale")),
        rbw_from_fft_size_hz=span_hz / fft_size if span_hz is not None and fft_size else None,
    )


def _simple_mapping(data: Mapping[str, Any]) -> dict[str, str | int | float | bool | None]:
    return {
        str(key): value
        for key, value in data.items()
        if isinstance(value, str | int | float | bool) or value is None
    }


def _float_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _int_or_none(value: Any) -> int | None:
    return int(value) if isinstance(value, int | float) else None


def _str_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def iter_frames_from_bytes(data: bytes, sample_format: str = "raw32") -> Iterator[IQFrame]:
    parser = AaroniaStreamParser(sample_format=sample_format)
    yield from parser.feed(data)
