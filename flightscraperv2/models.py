from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class FlightQuery:
    origin: str
    destination: str
    depart_date: str
    return_date: str | None = None
    trip_type: str = "round_trip"
    passengers: int = 1
    cabin: str = "economy"
    max_stops: int | None = None
    timeout_seconds: float = 45.0
    max_retries: int = 3


@dataclass(slots=True)
class FlightSegment:
    airline_code: str | None
    airline_name: str | None
    flight_number: str | None
    operating_airline: str | None
    origin_airport: str | None
    origin_name: str | None
    destination_airport: str | None
    destination_name: str | None
    departure_time: str | None
    arrival_time: str | None
    duration_minutes: int | None
    aircraft: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FlightOffer:
    origin_airport: str | None
    destination_airport: str | None
    departure_date: str | None
    arrival_date: str | None
    departure_time: str | None
    arrival_time: str | None
    duration_minutes: int | None
    stops: int | None
    price: int | None
    currency: str | None
    airlines: list[str] = field(default_factory=list)
    flight_numbers: list[str] = field(default_factory=list)
    layovers: list[dict[str, Any]] = field(default_factory=list)
    emissions_kg: int | None = None
    emissions_delta_percent: int | None = None
    booking_token: str | None = None
    is_best: bool | None = None
    segments: list[FlightSegment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["segments"] = [segment.to_dict() for segment in self.segments]
        return data


@dataclass(slots=True)
class NetworkCapture:
    url: str
    request_body: str | None
    response_body: str
    captured_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"),
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScrapeRun:
    query: FlightQuery
    final_url: str
    capture: NetworkCapture
    offers: list[FlightOffer]
    archive_dir: Path
    requested_mode: str = "browser"
    executed_mode: str = "browser"
    timings: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": asdict(self.query),
            "final_url": self.final_url,
            "capture": self.capture.to_dict(),
            "offers": [offer.to_dict() for offer in self.offers],
            "archive_dir": str(self.archive_dir),
            "requested_mode": self.requested_mode,
            "executed_mode": self.executed_mode,
            "timings": self.timings,
            "notes": self.notes,
        }
