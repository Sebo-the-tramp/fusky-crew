"""API authentication and payload tests."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import LocationReading
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
            "Access-Control-Request-Headers": "Authorization,skip_zrok_interstitial",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://example.test"
    assert "skip_zrok_interstitial" in allowed.headers["access-control-allow-headers"].lower()

    denied = client.options(
        "/api/location",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
