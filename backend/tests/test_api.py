"""API authentication and payload tests."""

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import LocationReading
from app.provider import LocationUnavailable, parse_garmin_livetrack_page
from app.settings import Settings


class FixedProvider:
    def __init__(self) -> None:
        self.fetch_count = 0

    def fetch(self) -> LocationReading:
        self.fetch_count += 1
        return LocationReading(
            device_name="Test tracker",
            latitude=46.29066,
            longitude=11.46283,
            reported_at=datetime.now(UTC),
            accuracy_m=8,
            source="test",
        )


def settings() -> Settings:
    return Settings(
        app_env="test",
        provider="mock",
        access_token="test-secret",
        allowed_origins=("https://example.test",),
        cache_seconds=30,
        stale_after_seconds=600,
        device_name="Test tracker",
        garmin_device_name="Test Forerunner",
        account_path=Path("unused"),
        device_path=Path("unused"),
        anisette_path=Path("unused"),
        mock_latitude=0,
        mock_longitude=0,
        mock_accuracy_m=0,
    )


def test_location_requires_bearer_token() -> None:
    client = TestClient(create_app(settings(), FixedProvider()))
    assert client.get("/api/location").status_code == 401
    assert client.get("/api/location", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_location_returns_minimal_payload_and_no_store() -> None:
    provider = FixedProvider()
    client = TestClient(create_app(settings(), provider))
    response = client.get(
        "/api/location",
        headers={"Authorization": "Bearer test-secret"},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["device_name"] == "Test tracker"
    assert response.json()["lat"] == 46.29066
    assert "key" not in response.json()

    # Repeated browser polling must not repeatedly hit Apple's upstream service.
    assert client.get(
        "/api/location",
        headers={"Authorization": "Bearer test-secret"},
    ).status_code == 200
    assert provider.fetch_count == 1


def test_cors_is_limited_to_configured_origin() -> None:
    client = TestClient(create_app(settings(), FixedProvider()))
    allowed = client.options(
        "/api/location",
        headers={
            "Origin": "https://example.test",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": (
                "Authorization,skip_zrok_interstitial,X-Garmin-LiveTrack-Url"
            ),
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://example.test"
    assert "skip_zrok_interstitial" in allowed.headers["access-control-allow-headers"].lower()
    assert "x-garmin-livetrack-url" in allowed.headers["access-control-allow-headers"].lower()

    denied = client.options(
        "/api/location",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_garmin_location_uses_authenticated_session_url() -> None:
    provider = FixedProvider()
    client = TestClient(
        create_app(
            settings(),
            FixedProvider(),
            garmin_provider_factory=lambda _url: provider,
        )
    )
    headers = {
        "Authorization": "Bearer test-secret",
        "X-Garmin-LiveTrack-Url": (
            "https://livetrack.garmin.com/session/test-session/token/test-token"
        ),
    }
    response = client.get("/api/garmin/location", headers=headers)
    assert response.status_code == 200
    assert response.json()["lat"] == 46.29066
    assert response.json()["source"] == "test"

    assert client.get(
        "/api/garmin/location",
        headers={"X-Garmin-LiveTrack-Url": headers["X-Garmin-LiveTrack-Url"]},
    ).status_code == 401


def test_garmin_location_rejects_non_garmin_url() -> None:
    client = TestClient(create_app(settings(), FixedProvider()))
    response = client.get(
        "/api/garmin/location",
        headers={
            "Authorization": "Bearer test-secret",
            "X-Garmin-LiveTrack-Url": "https://example.test/session/id/token/value",
        },
    )
    assert response.status_code == 400


def test_parse_garmin_livetrack_page_returns_newest_point() -> None:
    payload = {
        "pages": [
            {
                "trackPoints": [
                    {
                        "dateTime": "2026-09-25T09:12:01.000Z",
                        "position": {"lat": 46.27, "lon": 11.41},
                    },
                    {
                        "dateTime": "2026-09-25T09:12:11.000Z",
                        "position": {"lat": 46.28, "lon": 11.42},
                    },
                ]
            }
        ]
    }
    flight_chunk = [1, f"10:{json.dumps(payload)}"]
    page = f"<script>self.__next_f.push({json.dumps(flight_chunk)})</script>"

    reading = parse_garmin_livetrack_page(page, "Forerunner 965")
    assert reading.latitude == 46.28
    assert reading.longitude == 11.42
    assert reading.reported_at == datetime(2026, 9, 25, 9, 12, 11, tzinfo=UTC)
    assert reading.source == "garmin_livetrack"
    assert [(point.latitude, point.longitude) for point in reading.track] == [
        (46.27, 11.41),
        (46.28, 11.42),
    ]


def test_parse_garmin_livetrack_page_requires_position() -> None:
    try:
        parse_garmin_livetrack_page("<html></html>", "Forerunner 965")
    except LocationUnavailable:
        pass
    else:
        raise AssertionError("Expected a missing Garmin position to be rejected")


def test_parse_garmin_livetrack_page_reports_ended_session() -> None:
    flight_chunk = [1, '10:{"viewable":false,"trackPoints":[]}']
    page = f"<script>self.__next_f.push({json.dumps(flight_chunk)})</script>"
    try:
        parse_garmin_livetrack_page(page, "Forerunner 965")
    except LocationUnavailable as exc:
        assert str(exc) == "Garmin LiveTrack session has ended"
    else:
        raise AssertionError("Expected an ended Garmin session to be rejected")
