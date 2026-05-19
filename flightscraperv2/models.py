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
    detail_level: str = "summary"
    selected_offer_index: int | None = None
    selected_return_offer_index: int | None = None


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
class BookingOption:
    provider_code: str | None
    provider_name: str | None
    provider_display_domain: str | None
    provider_image_url: str | None
    price: int | None
    currency: str | None
    deeplink_url: str | None
    fare_name: str | None
    resolved_booking_url: str | None = None
    flight_codes: list[str] = field(default_factory=list)
    is_primary: bool | None = None
    raw_rank: int | None = None

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
    trip_type: str = "one_way"
    airlines: list[str] = field(default_factory=list)
    flight_numbers: list[str] = field(default_factory=list)
    layovers: list[dict[str, Any]] = field(default_factory=list)
    emissions_kg: int | None = None
    emissions_delta_percent: int | None = None
    booking_token: str | None = None
    is_best: bool | None = None
    segments: list[FlightSegment] = field(default_factory=list)
    return_origin_airport: str | None = None
    return_destination_airport: str | None = None
    return_departure_date: str | None = None
    return_arrival_date: str | None = None
    return_departure_time: str | None = None
    return_arrival_time: str | None = None
    return_duration_minutes: int | None = None
    return_stops: int | None = None
    return_airlines: list[str] = field(default_factory=list)
    return_flight_numbers: list[str] = field(default_factory=list)
    return_layovers: list[dict[str, Any]] = field(default_factory=list)
    return_segments: list[FlightSegment] = field(default_factory=list)
    booking_options: list[BookingOption] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["segments"] = [segment.to_dict() for segment in self.segments]
        data["return_segments"] = [segment.to_dict() for segment in self.return_segments]
        data["booking_options"] = [option.to_dict() for option in self.booking_options]
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
    supplemental_captures: list[NetworkCapture] = field(default_factory=list)
    requested_mode: str = "browser"
    executed_mode: str = "browser"
    timings: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": asdict(self.query),
            "final_url": self.final_url,
            "capture": self.capture.to_dict(),
            "supplemental_captures": [capture.to_dict() for capture in self.supplemental_captures],
            "offers": [offer.to_dict() for offer in self.offers],
            "archive_dir": str(self.archive_dir),
            "requested_mode": self.requested_mode,
            "executed_mode": self.executed_mode,
            "timings": self.timings,
            "notes": self.notes,
        }


@dataclass(slots=True)
class OfferDetails:
    query: FlightQuery
    final_url: str
    capture: NetworkCapture
    archive_dir: Path
    selected_offer_index: int
    selected_return_offer_index: int | None = None
    selected_outbound_offer: FlightOffer | None = None
    return_offers: list[FlightOffer] = field(default_factory=list)
    selected_itinerary: FlightOffer | None = None
    booking_options: list[BookingOption] = field(default_factory=list)
    supplemental_captures: list[NetworkCapture] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": asdict(self.query),
            "final_url": self.final_url,
            "capture": self.capture.to_dict(),
            "supplemental_captures": [capture.to_dict() for capture in self.supplemental_captures],
            "archive_dir": str(self.archive_dir),
            "selected_offer_index": self.selected_offer_index,
            "selected_return_offer_index": self.selected_return_offer_index,
            "selected_outbound_offer": self.selected_outbound_offer.to_dict() if self.selected_outbound_offer else None,
            "return_offers": [offer.to_dict() for offer in self.return_offers],
            "selected_itinerary": self.selected_itinerary.to_dict() if self.selected_itinerary else None,
            "booking_options": [option.to_dict() for option in self.booking_options],
            "timings": self.timings,
            "notes": self.notes,
        }
