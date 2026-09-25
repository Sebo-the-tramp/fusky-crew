"""Location providers and cache service."""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .models import LocationReading, TrackPointReading
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


GARMIN_LIVETRACK_HOSTS = {"livetrack.garmin.com"}
GARMIN_SESSION_PATH = re.compile(r"^/session/[^/]+/token/[^/]+/?$")
NEXT_FLIGHT_PUSH = re.compile(r"self\.__next_f\.push\((\[.*?\])\)</script>", re.DOTALL)


def validate_garmin_livetrack_url(value: str) -> str:
    """Validate a Garmin session capability URL before making a server-side request."""

    parsed = urlparse(value.strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname not in GARMIN_LIVETRACK_HOSTS
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or not GARMIN_SESSION_PATH.fullmatch(parsed.path)
    ):
        raise ValueError("Invalid Garmin LiveTrack session URL")
    return parsed._replace(fragment="").geturl()


def parse_garmin_livetrack_page(page: str, device_name: str) -> LocationReading:
    """Extract the newest public track point from Garmin's Next.js page payload."""

    decoder = json.JSONDecoder()
    points: list[dict[str, object]] = []
    session_ended = False
    for match in NEXT_FLIGHT_PUSH.finditer(page):
        try:
            flight_chunk = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if len(flight_chunk) < 2 or not isinstance(flight_chunk[1], str):
            continue

        payload = flight_chunk[1]
        session_ended = session_ended or '"viewable":false' in payload
        search_from = 0
        marker = '"trackPoints"'
        while (marker_at := payload.find(marker, search_from)) >= 0:
            colon_at = payload.find(":", marker_at + len(marker))
            if colon_at < 0:
                break
            array_at = colon_at + 1
            while array_at < len(payload) and payload[array_at].isspace():
                array_at += 1
            try:
                parsed_points, consumed = decoder.raw_decode(payload, array_at)
            except json.JSONDecodeError:
                search_from = array_at
                continue
            if isinstance(parsed_points, list):
                points.extend(point for point in parsed_points if isinstance(point, dict))
            search_from = array_at + consumed

    candidates: dict[tuple[datetime, float, float], TrackPointReading] = {}
    for point in points:
        position = point.get("position")
        reported = point.get("dateTime")
        if not isinstance(position, dict) or not isinstance(reported, str):
            continue
        try:
            timestamp = datetime.fromisoformat(reported)
            latitude = float(position["lat"])
            longitude = float(position["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            candidates[(timestamp, latitude, longitude)] = TrackPointReading(
                latitude=latitude,
                longitude=longitude,
                reported_at=timestamp,
            )

    if not candidates:
        if session_ended:
            raise LocationUnavailable("Garmin LiveTrack session has ended")
        raise LocationUnavailable("Garmin returned no public LiveTrack position")

    track = tuple(sorted(candidates.values(), key=lambda point: point.reported_at))
    newest = track[-1]
    return LocationReading(
        device_name=device_name,
        latitude=newest.latitude,
        longitude=newest.longitude,
        reported_at=newest.reported_at,
        accuracy_m=None,
        source="garmin_livetrack",
        track=track,
    )


class GarminLiveTrackProvider:
    """Read the newest point from a public Garmin LiveTrack session page."""

    def __init__(self, url: str, device_name: str) -> None:
        self._url = validate_garmin_livetrack_url(url)
        self._device_name = device_name

    def fetch(self) -> LocationReading:
        request = Request(
            self._url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "FUSKY-Crew-LiveTrack-Bridge/0.1",
            },
        )
        try:
            with urlopen(request, timeout=15) as response:
                page = response.read(12_000_001)
        except HTTPError as exc:
            raise LocationUnavailable(f"Garmin returned HTTP {exc.code}") from exc
        except (TimeoutError, URLError) as exc:
            raise LocationUnavailable("Unable to reach Garmin LiveTrack") from exc

        if len(page) > 12_000_000:
            raise LocationUnavailable("Garmin LiveTrack response was unexpectedly large")
        return parse_garmin_livetrack_page(page.decode("utf-8", errors="replace"), self._device_name)


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


class GarminLiveTrackService:
    """Cache a small number of session-specific Garmin providers."""

    def __init__(
        self,
        ttl_seconds: int,
        provider_factory: Callable[[str], LocationProvider],
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._provider_factory = provider_factory
        self._lock = threading.Lock()
        self._services: dict[str, CachedLocationService] = {}

    def get(self, url: str) -> LocationReading:
        normalized = validate_garmin_livetrack_url(url)
        with self._lock:
            service = self._services.get(normalized)
            if service is None:
                if len(self._services) >= 8:
                    self._services.pop(next(iter(self._services)))
                service = CachedLocationService(
                    self._provider_factory(normalized),
                    self._ttl_seconds,
                )
                self._services[normalized] = service
        return service.get()


def build_provider(settings: Settings) -> LocationProvider:
    """Build the configured provider."""

    if settings.provider == "findmy":
        return FindMyLocationProvider(settings)
    return MockLocationProvider(settings)
