from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class HotelQuery:
    destination: str
    check_in: str
    check_out: str
    adults: int = 2
    children: int = 0
    rooms: int = 1
    currency: str | None = None
    max_price: int | None = None
    timeout_seconds: float = 45.0
    max_retries: int = 3


@dataclass(slots=True)
class RoomOffer:
    room_name: str | None
    price: int | None
    currency: str | None
    taxes_and_fees: int | None = None
    cancellation_policy: str | None = None
    booking_token: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HotelOffer:
    property_id: str | None
    name: str | None
    address: str | None
    neighborhood: str | None
    review_score: float | None
    review_count: int | None
    nightly_price: int | None
    total_price: int | None
    currency: str | None
    latitude: float | None = None
    longitude: float | None = None
    amenities: list[str] = field(default_factory=list)
    room_offers: list[RoomOffer] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["room_offers"] = [offer.to_dict() for offer in self.room_offers]
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
    query: HotelQuery
    final_url: str
    capture: NetworkCapture
    offers: list[HotelOffer]
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
