"""Location providers and cache service."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Protocol

from .models import LocationReading
from .settings import Settings


class LocationUnavailable(RuntimeError):
    """Raised when a provider cannot return a location."""


class LocationProvider(Protocol):
    """Interface implemented by location sources."""

    def fetch(self) -> LocationReading:
        """Return the newest known reading."""


class MockLocationProvider:
    """Safe provider for development without Apple credentials."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch(self) -> LocationReading:
        return LocationReading(
            device_name=self._settings.device_name,
            latitude=self._settings.mock_latitude,
            longitude=self._settings.mock_longitude,
            reported_at=datetime.now(UTC),
            accuracy_m=self._settings.mock_accuracy_m,
            source="mock",
        )


class FindMyLocationProvider:
    """FindMy.py adapter; imports the optional integration only when selected."""

    def __init__(self, settings: Settings) -> None:
        from findmy import AppleAccount, FindMyAccessory

        missing = [
            path
            for path in (settings.account_path, settings.device_path)
            if not path.is_file()
        ]
        if missing:
            paths = ", ".join(str(path) for path in missing)
            raise FileNotFoundError(f"Missing Find My secret file(s): {paths}")

        self._settings = settings
        self._account = AppleAccount.from_json(
            settings.account_path,
            anisette_libs_path=str(settings.anisette_path),
        )
        self._device = FindMyAccessory.from_json(settings.device_path)

    def fetch(self) -> LocationReading:
        report = self._account.fetch_location(self._device)
        if report is None:
            raise LocationUnavailable("Apple returned no location report for this device")

        # FindMy.py updates alignment/session state while fetching. Keep those updates server-side.
        self._account.to_json(self._settings.account_path)
        self._device.to_json(self._settings.device_path)

        return LocationReading(
            device_name=self._settings.device_name,
            latitude=report.latitude,
            longitude=report.longitude,
            reported_at=report.timestamp,
            accuracy_m=report.horizontal_accuracy,
            source="findmy",
        )


class CachedLocationService:
    """Serialize upstream queries and reuse recent results."""

    def __init__(self, provider: LocationProvider, ttl_seconds: int) -> None:
        self._provider = provider
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._cached: LocationReading | None = None
        self._cached_at = 0.0

    def get(self) -> LocationReading:
        now = time.monotonic()
        if self._cached is not None and now - self._cached_at < self._ttl_seconds:
            return self._cached

        with self._lock:
            now = time.monotonic()
            if self._cached is not None and now - self._cached_at < self._ttl_seconds:
                return self._cached
            reading = self._provider.fetch()
            self._cached = reading
            self._cached_at = time.monotonic()
            return reading


def build_provider(settings: Settings) -> LocationProvider:
    """Build the configured provider."""

    if settings.provider == "findmy":
        return FindMyLocationProvider(settings)
    return MockLocationProvider(settings)
