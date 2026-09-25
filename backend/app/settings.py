"""Environment-backed service settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    """Validated application settings."""

    app_env: str
    provider: str
    access_token: str
    allowed_origins: tuple[str, ...]
    cache_seconds: int
    stale_after_seconds: int
    device_name: str
    garmin_device_name: str
    account_path: Path
    device_path: Path
    anisette_path: Path
    mock_latitude: float
    mock_longitude: float
    mock_accuracy_m: int

    @classmethod
    def from_env(cls) -> Settings:
        settings = cls(
            app_env=os.getenv("APP_ENV", "development").lower(),
            provider=os.getenv("LOCATION_PROVIDER", "mock").lower(),
            access_token=os.getenv("TRACKING_ACCESS_TOKEN", "dev-only-change-me"),
            allowed_origins=_csv(
                os.getenv(
                    "ALLOWED_ORIGINS",
                    "http://localhost:4321,http://127.0.0.1:4321",
                )
            ),
            cache_seconds=max(5, int(os.getenv("CACHE_SECONDS", "30"))),
            stale_after_seconds=max(60, int(os.getenv("STALE_AFTER_SECONDS", "600"))),
            device_name=os.getenv("DEVICE_NAME", "FUSKY tracker"),
            garmin_device_name=os.getenv("GARMIN_DEVICE_NAME", "Garmin Forerunner 965"),
            account_path=Path(os.getenv("FINDMY_ACCOUNT_PATH", "secrets/account.json")),
            device_path=Path(os.getenv("FINDMY_DEVICE_PATH", "secrets/device.json")),
            anisette_path=Path(os.getenv("FINDMY_ANISETTE_PATH", "secrets/ani_libs.bin")),
            mock_latitude=float(os.getenv("MOCK_LAT", "46.29066")),
            mock_longitude=float(os.getenv("MOCK_LON", "11.46283")),
            mock_accuracy_m=max(0, int(os.getenv("MOCK_ACCURACY_M", "12"))),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.provider not in {"mock", "findmy"}:
            raise ValueError("LOCATION_PROVIDER must be 'mock' or 'findmy'")
        if self.app_env == "production" and len(self.access_token) < 24:
            raise ValueError("Production TRACKING_ACCESS_TOKEN must be at least 24 characters")
        if self.app_env == "production" and not self.allowed_origins:
            raise ValueError("Production ALLOWED_ORIGINS cannot be empty")
        if self.app_env == "production" and "*" in self.allowed_origins:
            raise ValueError("Wildcard CORS origins are not allowed in production")
