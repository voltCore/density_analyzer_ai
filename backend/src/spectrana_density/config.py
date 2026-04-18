from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration.

    Defaults are intentionally safe for local development. Set SOURCE_MODE=aaronia
    when a SPECTRAN/RTSA HTTP server is reachable.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Spectrana Density"
    source_mode: Literal["mock", "aaronia"] = "mock"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    aaronia_stream_url: str = "http://localhost:54664/stream?format=raw32"
    aaronia_control_url: str = "http://localhost:54665/control"
    aaronia_control_method: Literal["PUT", "POST"] = "PUT"
    aaronia_receiver_name: str | None = None

    request_timeout_seconds: float = Field(default=10.0, gt=0)
    stream_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    stream_read_timeout_seconds: float = Field(default=15.0, gt=0)
    max_capture_samples: int = Field(default=262_144, ge=1024)

    default_bins: int = Field(default=1024, ge=16, le=65_536)
    default_capture_seconds: float = Field(default=0.25, gt=0)
    default_frequency_from_hz: float = Field(default=2_400_000_000, gt=0)
    default_frequency_to_hz: float = Field(default=2_500_000_000, gt=0)
    database_path: str = "data/spectrana_density.sqlite3"

    ai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AI_API_KEY", "OPENAI_API_KEY"),
    )
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-5-mini"
    ai_timeout_seconds: float = Field(default=90.0, gt=0)

    @property
    def control_url(self) -> AnyHttpUrl | str:
        return self.aaronia_control_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
