from __future__ import annotations

import json
from urllib.parse import urlencode

from .models import FlightOffer, FlightSegment


def build_booking_request_body(offer: FlightOffer) -> str:
    if not offer.booking_token:
        raise ValueError("Round-trip offer is missing a booking token.")
    if not offer.segments:
        raise ValueError("Booking replay requires at least one segment.")

    legs = [_build_leg(offer.segments)]
    if offer.return_segments:
        legs.append(_build_leg(offer.return_segments))
    payload = [
        None,
        json.dumps(
            [
                [None, offer.booking_token],
                [
                    None,
                    None,
                    1,
                    None,
                    [],
                    1,
                    [1, 0, 0, 0],
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    legs,
                    None,
                    None,
                    None,
                    1,
                ],
                None,
                1,
            ],
            separators=(",", ":"),
        ),
    ]
    return urlencode({"f.req": json.dumps(payload, separators=(",", ":"))})


def _build_leg(segments: list[FlightSegment]) -> list:
    first = segments[0]
    last = segments[-1]
    depart_date = _date_part(first.departure_time)
    if not first.origin_airport or not last.destination_airport or not depart_date:
        raise ValueError("Segment data is incomplete for booking replay.")
    flights = [_build_flight_descriptor(segment) for segment in segments]
    return [
        [[[first.origin_airport, 0]]],
        [[[last.destination_airport, 0]]],
        None,
        0,
        None,
        None,
        depart_date,
        None,
        flights,
        None,
        None,
        None,
        None,
        None,
        3,
    ]


def _build_flight_descriptor(segment: FlightSegment) -> list:
    depart_date = _date_part(segment.departure_time)
    if not (
        segment.origin_airport
        and depart_date
        and segment.destination_airport
        and segment.airline_code
        and segment.flight_number
    ):
        raise ValueError("Flight segment is incomplete for booking replay.")
    return [
        segment.origin_airport,
        depart_date,
        segment.destination_airport,
        None,
        segment.airline_code,
        segment.flight_number,
    ]


def _date_part(timestamp: str | None) -> str | None:
    if timestamp is None or "T" not in timestamp:
        return None
    return timestamp.split("T", 1)[0]
