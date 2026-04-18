import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from spectrana_density.schemas import (
    MeasurementCreate,
    MeasurementStored,
    MeasurementSummary,
)


class MeasurementStore:
    def __init__(self, database_path: str) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def create(self, payload: MeasurementCreate) -> MeasurementStored:
        measurement_id = str(uuid4())
        created_at = datetime.now(tz=UTC).isoformat()
        name = _measurement_name(payload, created_at)
        result_json = payload.result.model_dump_json()
        device_status_json = (
            payload.device_status.model_dump_json() if payload.device_status is not None else None
        )

        summary = _summary_from_payload(
            measurement_id=measurement_id,
            name=name,
            created_at=created_at,
            payload=payload,
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO measurements (
                    id, name, created_at, source, frequency_from_hz, frequency_to_hz,
                    center_frequency_hz, span_hz, bins, occupancy_percent,
                    occupied_bandwidth_hz, mean_density_db_per_hz, peak_density_db_per_hz,
                    integrated_power_db, peak_frequency_hz, bins_count, result_json,
                    device_status_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.id,
                    summary.name,
                    summary.created_at,
                    summary.source,
                    summary.frequency_from_hz,
                    summary.frequency_to_hz,
                    summary.center_frequency_hz,
                    summary.span_hz,
                    summary.bins,
                    summary.occupancy_percent,
                    summary.occupied_bandwidth_hz,
                    summary.mean_density_db_per_hz,
                    summary.peak_density_db_per_hz,
                    summary.integrated_power_db,
                    summary.peak_frequency_hz,
                    summary.bins_count,
                    result_json,
                    device_status_json,
                ),
            )

        return self.get(measurement_id)

    def list(self) -> list[MeasurementSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, created_at, source, frequency_from_hz, frequency_to_hz,
                       center_frequency_hz, span_hz, bins, occupancy_percent,
                       occupied_bandwidth_hz, mean_density_db_per_hz, peak_density_db_per_hz,
                       integrated_power_db, peak_frequency_hz, bins_count
                FROM measurements
                ORDER BY created_at DESC
                """
            ).fetchall()

        return [_summary_from_row(row) for row in rows]

    def get(self, measurement_id: str) -> MeasurementStored:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, name, created_at, source, frequency_from_hz, frequency_to_hz,
                       center_frequency_hz, span_hz, bins, occupancy_percent,
                       occupied_bandwidth_hz, mean_density_db_per_hz, peak_density_db_per_hz,
                       integrated_power_db, peak_frequency_hz, bins_count, result_json,
                       device_status_json
                FROM measurements
                WHERE id = ?
                """,
                (measurement_id,),
            ).fetchone()

        if row is None:
            msg = f"Measurement {measurement_id} was not found"
            raise KeyError(msg)

        summary = _summary_from_row(row)
        result = json.loads(row["result_json"])
        device_status = json.loads(row["device_status_json"]) if row["device_status_json"] else None
        return MeasurementStored(
            **summary.model_dump(),
            result=result,
            device_status=device_status,
        )

    def delete(self, measurement_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM measurements WHERE id = ?", (measurement_id,))

        if cursor.rowcount == 0:
            msg = f"Measurement {measurement_id} was not found"
            raise KeyError(msg)

    @contextmanager
    def _connect(self) -> Any:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS measurements (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    frequency_from_hz REAL NOT NULL,
                    frequency_to_hz REAL NOT NULL,
                    center_frequency_hz REAL NOT NULL,
                    span_hz REAL NOT NULL,
                    bins INTEGER NOT NULL,
                    occupancy_percent REAL NOT NULL,
                    occupied_bandwidth_hz REAL NOT NULL,
                    mean_density_db_per_hz REAL NOT NULL,
                    peak_density_db_per_hz REAL NOT NULL,
                    integrated_power_db REAL NOT NULL,
                    peak_frequency_hz REAL NOT NULL,
                    bins_count INTEGER NOT NULL,
                    result_json TEXT NOT NULL,
                    device_status_json TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_measurements_created_at
                ON measurements(created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_measurements_frequency_range
                ON measurements(frequency_from_hz, frequency_to_hz)
                """
            )


def _summary_from_payload(
    *,
    measurement_id: str,
    name: str,
    created_at: str,
    payload: MeasurementCreate,
) -> MeasurementSummary:
    result = payload.result
    return MeasurementSummary(
        id=measurement_id,
        name=name,
        created_at=created_at,
        source=result.source,
        frequency_from_hz=result.capture_settings.frequency_from_hz,
        frequency_to_hz=result.capture_settings.frequency_to_hz,
        center_frequency_hz=result.capture_settings.center_frequency_hz,
        span_hz=result.capture_settings.span_hz,
        bins=result.capture_settings.bins,
        occupancy_percent=result.range_assessment.occupancy_percent,
        occupied_bandwidth_hz=result.range_assessment.occupied_bandwidth_hz,
        mean_density_db_per_hz=result.summary.mean_density_db_per_hz,
        peak_density_db_per_hz=result.summary.peak_density_db_per_hz,
        integrated_power_db=result.summary.integrated_power_db,
        peak_frequency_hz=result.summary.peak_frequency_hz,
        bins_count=len(result.bins),
    )


def _summary_from_row(row: sqlite3.Row) -> MeasurementSummary:
    return MeasurementSummary(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        source=row["source"],
        frequency_from_hz=row["frequency_from_hz"],
        frequency_to_hz=row["frequency_to_hz"],
        center_frequency_hz=row["center_frequency_hz"],
        span_hz=row["span_hz"],
        bins=row["bins"],
        occupancy_percent=row["occupancy_percent"],
        occupied_bandwidth_hz=row["occupied_bandwidth_hz"],
        mean_density_db_per_hz=row["mean_density_db_per_hz"],
        peak_density_db_per_hz=row["peak_density_db_per_hz"],
        integrated_power_db=row["integrated_power_db"],
        peak_frequency_hz=row["peak_frequency_hz"],
        bins_count=row["bins_count"],
    )


def _measurement_name(payload: MeasurementCreate, created_at: str) -> str:
    if payload.name and payload.name.strip():
        return payload.name.strip()

    result = payload.result
    start_mhz = result.capture_settings.frequency_from_hz / 1_000_000
    end_mhz = result.capture_settings.frequency_to_hz / 1_000_000
    density = result.range_assessment.occupancy_percent
    timestamp = datetime.fromisoformat(created_at).strftime("%Y-%m-%d %H:%M:%S")
    return f"{timestamp} · {start_mhz:.3f}-{end_mhz:.3f} MHz · {density:.3f}%"
