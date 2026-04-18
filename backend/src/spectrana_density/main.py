from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from spectrana_density.ai_agent import (
    AIComparisonUnavailableError,
    explain_signal_comparison,
)
from spectrana_density.config import Settings, get_settings
from spectrana_density.schemas import (
    AIComparisonRequest,
    AIComparisonResponse,
    BinDensity,
    CaptureSettings,
    DensityRequest,
    DensityResponse,
    DensitySummary,
    DeviceStatusResponse,
    MeasurementCreate,
    MeasurementStored,
    MeasurementSummary,
    RangeAssessment,
    SettingsResponse,
)
from spectrana_density.signal.density import assess_range_density, compute_density
from spectrana_density.sources.aaronia import mock_device_status, read_aaronia_device_status
from spectrana_density.sources.factory import create_source
from spectrana_density.storage import MeasurementStore


def create_app() -> FastAPI:
    settings = get_settings()
    store = MeasurementStore(settings.database_path)
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/settings")
    async def read_settings(
        runtime_settings: Annotated[Settings, Depends(get_settings)],
    ) -> SettingsResponse:
        return SettingsResponse(
            app_name=runtime_settings.app_name,
            source_mode=runtime_settings.source_mode,
            default_frequency_from_hz=runtime_settings.default_frequency_from_hz,
            default_frequency_to_hz=runtime_settings.default_frequency_to_hz,
            default_bins=runtime_settings.default_bins,
            default_capture_seconds=runtime_settings.default_capture_seconds,
            max_capture_samples=runtime_settings.max_capture_samples,
            ai_model=runtime_settings.ai_model,
            ai_explanation_enabled=bool(runtime_settings.ai_api_key),
        )

    @app.get("/api/device/status")
    async def read_device_status(
        runtime_settings: Annotated[Settings, Depends(get_settings)],
    ) -> DeviceStatusResponse:
        if runtime_settings.source_mode == "mock":
            return mock_device_status(runtime_settings)
        return await read_aaronia_device_status(runtime_settings)

    @app.get("/api/measurements")
    async def list_measurements() -> list[MeasurementSummary]:
        return store.list()

    @app.post("/api/measurements")
    async def create_measurement(payload: MeasurementCreate) -> MeasurementStored:
        return store.create(payload)

    @app.get("/api/measurements/{measurement_id}")
    async def read_measurement(measurement_id: str) -> MeasurementStored:
        try:
            return store.get(measurement_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/measurements/{measurement_id}")
    async def delete_measurement(measurement_id: str) -> dict[str, bool]:
        try:
            store.delete(measurement_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": True}

    @app.post("/api/comparisons/ai-explanation")
    async def explain_comparison(
        payload: AIComparisonRequest,
        runtime_settings: Annotated[Settings, Depends(get_settings)],
    ) -> AIComparisonResponse:
        try:
            return await explain_signal_comparison(payload, runtime_settings)
        except AIComparisonUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/density")
    async def calculate_density(
        request: DensityRequest,
        runtime_settings: Annotated[Settings, Depends(get_settings)],
    ) -> DensityResponse:
        source = create_source(runtime_settings)
        try:
            capture = await source.capture(request)
            result = capture.density or compute_density(
                capture.samples,
                frequency_from_hz=capture.frequency_from_hz,
                frequency_to_hz=capture.frequency_to_hz,
                bins=request.bins,
                window=request.window,
            )
            assessment = assess_range_density(
                result.density_db_per_hz,
                bin_width_hz=result.bin_width_hz,
                threshold_offset_db=request.occupancy_threshold_db,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        density_unit = "V^2/Hz" if capture.unit.lower() in {"v", "volt", "volts"} else "unit^2/Hz"
        power_unit = "V^2" if capture.unit.lower() in {"v", "volt", "volts"} else "unit^2"
        sample_count = (
            capture.sample_count if capture.sample_count is not None else int(capture.samples.size)
        )
        summary = DensitySummary(
            frequency_from_hz=capture.frequency_from_hz,
            frequency_to_hz=capture.frequency_to_hz,
            center_frequency_hz=(capture.frequency_from_hz + capture.frequency_to_hz) / 2,
            span_hz=capture.frequency_to_hz - capture.frequency_from_hz,
            sample_rate_hz=capture.sample_rate_hz,
            sample_count=sample_count,
            bin_count=request.bins,
            bin_width_hz=result.bin_width_hz,
            averaged_segments=result.averaged_segments,
            density_unit=density_unit,
            power_unit=power_unit,
            mean_density_linear=result.mean_density_linear,
            mean_density_db_per_hz=result.mean_density_db_per_hz,
            peak_density_linear=result.peak_density_linear,
            peak_density_db_per_hz=result.peak_density_db_per_hz,
            peak_frequency_hz=result.peak_frequency_hz,
            integrated_power_linear=result.integrated_power_linear,
            integrated_power_db=result.integrated_power_db,
        )
        capture_settings = CaptureSettings(
            frequency_from_hz=capture.frequency_from_hz,
            frequency_to_hz=capture.frequency_to_hz,
            center_frequency_hz=(capture.frequency_from_hz + capture.frequency_to_hz) / 2,
            span_hz=capture.frequency_to_hz - capture.frequency_from_hz,
            rbw_estimate_hz=result.bin_width_hz,
            sample_rate_hz=capture.sample_rate_hz,
            bins=request.bins,
            reference_level_dbm=request.reference_level_dbm,
            occupancy_threshold_db=request.occupancy_threshold_db,
            capture_seconds=request.capture_seconds,
            window=request.window,
        )
        range_assessment = RangeAssessment(
            method=assessment.method,
            threshold_offset_db=assessment.threshold_offset_db,
            noise_floor_db_per_hz=assessment.noise_floor_db_per_hz,
            threshold_db_per_hz=assessment.threshold_db_per_hz,
            occupied_bins=assessment.occupied_bins,
            occupancy_percent=assessment.occupancy_percent,
            occupied_bandwidth_hz=assessment.occupied_bandwidth_hz,
            mean_excess_db=assessment.mean_excess_db,
            peak_to_floor_db=assessment.peak_to_floor_db,
            label=assessment.label,
        )

        bins = (
            [
                BinDensity(
                    index=index,
                    frequency_hz=float(result.frequencies_hz[index]),
                    density_linear=float(result.density_linear[index]),
                    density_db_per_hz=float(result.density_db_per_hz[index]),
                    power_linear=float(result.power_linear[index]),
                    power_db=float(result.power_db[index]),
                )
                for index in range(request.bins)
            ]
            if request.include_bins
            else []
        )

        return DensityResponse(
            source=runtime_settings.source_mode,
            configured_device=capture.configured_device,
            summary=summary,
            capture_settings=capture_settings,
            range_assessment=range_assessment,
            bins=bins,
            metadata={
                **capture.metadata,
                "packet_count": capture.packet_count,
                "iq_unit": capture.unit,
            },
        )

    return app


app = create_app()
