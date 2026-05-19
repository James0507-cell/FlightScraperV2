from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .cli import run_report, run_single


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


class HealthResponse(BaseModel):
    status: str
    service: str


def create_app() -> FastAPI:
    app = FastAPI(
        title="FlightScraperV2 API",
        version="0.1.0",
        description="HTTP API for Google Flights scraping and stored scrape reports.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {
            "service": "FlightScraperV2 API",
            "version": "0.1.0",
            "docs_url": "/docs",
            "openapi_url": "/openapi.json",
        }

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="FlightScraperV2 API")

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
        )
        payload = run.to_dict()
        payload["offer_count"] = len(run.offers)
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
