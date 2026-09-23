"""FastAPI entry point for the protected location bridge."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import HealthResponse, LocationResponse
from .provider import CachedLocationService, LocationProvider, LocationUnavailable, build_provider
from .settings import Settings

bearer = HTTPBearer(auto_error=False)


def create_app(
    settings: Settings | None = None,
    provider: LocationProvider | None = None,
) -> FastAPI:
    """Create an app, allowing provider injection for tests."""

    config = settings or Settings.from_env()
    source = provider or build_provider(config)
    service = CachedLocationService(source, config.cache_seconds)
    docs_enabled = config.app_env != "production"
    application = FastAPI(
        title="FUSKY tracking bridge",
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "skip_zrok_interstitial"],
        max_age=600,
    )

    def require_token(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(bearer),
        ] = None,
    ) -> None:
        supplied = credentials.credentials if credentials else ""
        if not hmac.compare_digest(supplied, config.access_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @application.middleware("http")
    async def privacy_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", provider=config.provider)

    @application.get(
        "/api/location",
        response_model=LocationResponse,
        dependencies=[Depends(require_token)],
    )
    def location(response: Response) -> LocationResponse:
        try:
            reading = service.get()
        except LocationUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Location provider failed") from exc

        fetched_at = datetime.now(UTC)
        reported_at = reading.reported_at
        if reported_at.tzinfo is None:
            reported_at = reported_at.replace(tzinfo=UTC)
        age_seconds = (fetched_at - reported_at.astimezone(UTC)).total_seconds()
        response.headers["X-Location-Age-Seconds"] = str(max(0, int(age_seconds)))
        return LocationResponse(
            device_name=reading.device_name,
            lat=reading.latitude,
            lon=reading.longitude,
            reported_at=reported_at,
            fetched_at=fetched_at,
            accuracy_m=reading.accuracy_m,
            source=reading.source,
            stale=age_seconds > config.stale_after_seconds,
        )

    return application


app = create_app()
