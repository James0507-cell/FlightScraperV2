from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .cli import run_report, run_single
from .models import FlightQuery
from .session_manager import SessionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api")

_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        raise HTTPException(status_code=503, detail="Session manager not initialized")
    return _session_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _session_manager
    _session_manager = SessionManager(headless=True, archive_root="artifacts")
    await _session_manager.start()
    logger.info("Session manager started")
    yield
    if _session_manager:
        await _session_manager.stop()
        logger.info("Session manager stopped")
    _session_manager = None


class ScrapeRequest(BaseModel):
    mode: Literal["auto", "browser", "replay"] = "auto"
    origin: str = Field(..., min_length=3)
    destination: str = Field(..., min_length=3)
    depart_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    return_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    passengers: int = Field(default=1, ge=1, le=9)
    cabin: Literal["economy", "premium_economy", "business", "first"] = "economy"
    max_stops: int | None = Field(default=None, ge=0, le=2)
    retries: int = Field(default=3, ge=1, le=5)
    archive_root: str = "artifacts"
    headless: bool = True
    detail_level: Literal["summary", "complete"] = "summary"


class SessionScrapeRequest(ScrapeRequest):
    session_ttl: int = Field(default=600, ge=60, le=3600, description="Session lifetime in seconds")


class OfferDetailsRequest(ScrapeRequest):
    offer_index: int = Field(..., ge=0)
    return_offer_index: int | None = Field(default=None, ge=0)


class SessionDetailsRequest(BaseModel):
    offer_index: int = Field(..., ge=0)
    return_offer_index: int | None = Field(default=None, ge=0)


class HealthResponse(BaseModel):
    status: str
    service: str


def create_app() -> FastAPI:
    app = FastAPI(
        title="FlightScraperV2 API",
        version="0.2.0",
        description="HTTP API for Google Flights scraping with session-based detail fetching.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info(f"Incoming Request - Method: {request.method} Path: {request.url.path}")
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(
            f"Request Completed - Method: {request.method} Path: {request.url.path} "
            f"Status: {response.status_code} Duration: {duration:.2f}s"
        )
        return response

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {
            "service": "FlightScraperV2 API",
            "version": "0.2.0",
            "docs_url": "/docs",
            "openapi_url": "/openapi.json",
        }

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="FlightScraperV2 API")

    # === Session endpoints ===

    @app.post("/api/v1/sessions", tags=["sessions"])
    async def create_session(request: SessionScrapeRequest) -> dict:
        sm = get_session_manager()
        trip_type = "round_trip" if request.return_date else "one_way"
        query = FlightQuery(
            origin=request.origin,
            destination=request.destination,
            depart_date=request.depart_date,
            return_date=request.return_date,
            trip_type=trip_type,
            passengers=request.passengers,
            cabin=request.cabin,
            max_stops=request.max_stops,
            max_retries=request.retries,
            detail_level=request.detail_level,
        )
        session = await sm.create_session(query)
        return {
            "session_id": session.session_id,
            "origin": session.query.origin,
            "destination": session.query.destination,
            "depart_date": session.query.depart_date,
            "return_date": session.query.return_date,
            "offer_count": len(session.offers),
            "offers": [offer.to_dict() for offer in session.offers],
            "expires_at": session.expires_at.isoformat(),
            "notes": session.notes,
        }

    @app.get("/api/v1/sessions", tags=["sessions"])
    async def list_sessions() -> dict:
        sm = get_session_manager()
        sessions = await sm.list_sessions()
        return {"sessions": sessions, "count": len(sessions)}

    @app.get("/api/v1/sessions/{session_id}", tags=["sessions"])
    async def get_session(session_id: str) -> dict:
        sm = get_session_manager()
        session = await sm.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found or expired")
        return {
            "session_id": session.session_id,
            "origin": session.query.origin,
            "destination": session.query.destination,
            "depart_date": session.query.depart_date,
            "return_date": session.query.return_date,
            "offer_count": len(session.offers),
            "offers": [offer.to_dict() for offer in session.offers],
            "expires_at": session.expires_at.isoformat(),
            "notes": session.notes,
        }

    @app.delete("/api/v1/sessions/{session_id}", tags=["sessions"])
    async def delete_session(session_id: str) -> dict:
        sm = get_session_manager()
        deleted = await sm.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return {"session_id": session_id, "status": "deleted"}

    @app.post("/api/v1/sessions/{session_id}/details", tags=["sessions"])
    async def get_session_details(session_id: str, request: SessionDetailsRequest) -> dict:
        sm = get_session_manager()
        result = await sm.get_offer_details(
            session_id=session_id,
            offer_index=request.offer_index,
            return_offer_index=request.return_offer_index,
        )
        if result is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found or expired")
        payload = result.to_dict()
        payload["return_offer_count"] = len(result.return_offers)
        payload["booking_option_count"] = len(result.booking_options)
        return payload

    # === Legacy scrape endpoints (still supported) ===

    @app.post("/api/v1/scrape", tags=["scrape"])
    async def scrape(request: ScrapeRequest) -> dict:
        run = await run_single(
            mode=request.mode,
            origin=request.origin,
            destination=request.destination,
            depart_date=request.depart_date,
            return_date=request.return_date,
            passengers=request.passengers,
            cabin=request.cabin,
            max_stops=request.max_stops,
            headless=request.headless,
            archive_root=request.archive_root,
            max_retries=request.retries,
            detail_level=request.detail_level,
        )
        payload = run.to_dict()
        payload["offer_count"] = len(run.offers)
        return payload

    @app.post("/api/v1/scrape/details", tags=["scrape"])
    async def scrape_details(request: OfferDetailsRequest) -> dict:
        result = await run_single(
            mode="browser",
            origin=request.origin,
            destination=request.destination,
            depart_date=request.depart_date,
            return_date=request.return_date,
            passengers=request.passengers,
            cabin=request.cabin,
            max_stops=request.max_stops,
            headless=request.headless,
            archive_root=request.archive_root,
            max_retries=request.retries,
            detail_level=request.detail_level,
            selected_offer_index=request.offer_index,
            selected_return_offer_index=request.return_offer_index,
        )
        payload = result.to_dict()
        payload["return_offer_count"] = len(result.return_offers)
        payload["booking_option_count"] = len(result.booking_options)
        return payload

    @app.get("/api/v1/reports/recent-runs", tags=["reports"])
    async def recent_runs(
        limit: int = Query(default=10, ge=1, le=100),
        archive_root: str = Query(default="artifacts"),
        db_path: str | None = Query(default=None),
    ) -> dict:
        return _run_report(
            report_name="recent-runs",
            archive_root=archive_root,
            db_path=db_path,
            limit=limit,
        )

    @app.get("/api/v1/reports/cheapest-offers", tags=["reports"])
    async def cheapest_offers(
        limit: int = Query(default=10, ge=1, le=100),
        origin: str | None = Query(default=None),
        destination: str | None = Query(default=None),
        depart_date: str | None = Query(default=None),
        archive_root: str = Query(default="artifacts"),
        db_path: str | None = Query(default=None),
    ) -> dict:
        return _run_report(
            report_name="cheapest-offers",
            archive_root=archive_root,
            db_path=db_path,
            limit=limit,
            origin=origin,
            destination=destination,
            depart_date=depart_date,
        )

    @app.get("/api/v1/reports/mode-summary", tags=["reports"])
    async def mode_summary(
        archive_root: str = Query(default="artifacts"),
        db_path: str | None = Query(default=None),
    ) -> dict:
        return _run_report(
            report_name="mode-summary",
            archive_root=archive_root,
            db_path=db_path,
            limit=10,
        )

    return app


def _run_report(
    report_name: str,
    archive_root: str,
    db_path: str | None,
    limit: int,
    origin: str | None = None,
    destination: str | None = None,
    depart_date: str | None = None,
) -> dict:
    target_db = db_path or str(Path(archive_root) / "scraper.sqlite")
    try:
        return run_report(
            report_name=report_name,
            db_path=target_db,
            limit=limit,
            origin=origin,
            destination=destination,
            depart_date=depart_date,
        )
    except SystemExit as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


app = create_app()
