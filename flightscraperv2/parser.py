from __future__ import annotations

import json
from typing import Any

from .models import FlightOffer, FlightSegment

XSSI_PREFIX = ")]}'"


def strip_xssi_prefix(payload: str) -> str:
    stripped = payload.lstrip()
    if stripped.startswith(XSSI_PREFIX):
        stripped = stripped[len(XSSI_PREFIX):].lstrip()
    return stripped


def parse_google_payload(payload: str) -> list[Any]:
    stripped = strip_xssi_prefix(payload)
    parsed_lines: list[Any] = []
    for line in stripped.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        if candidate.isdigit():
            continue
        if not candidate.startswith("["):
            continue
        try:
            parsed_lines.append(json.loads(candidate))
        except json.JSONDecodeError:
            continue
    return parsed_lines


def extract_offers(payload: str, currency: str = "PHP") -> list[FlightOffer]:
    parsed_lines = parse_google_payload(payload)
    offers: list[FlightOffer] = []
    seen_tokens: set[str] = set()
    for parsed_line in parsed_lines:
        for node in _walk(parsed_line):
            offer = _parse_offer_candidate(node, currency=currency)
            if offer is None:
                continue
            if offer.booking_token and offer.booking_token in seen_tokens:
                continue
            if offer.booking_token:
                seen_tokens.add(offer.booking_token)
            offers.append(offer)
    return offers


def _walk(node: Any):
    if isinstance(node, list):
        yield node
        for child in node:
            yield from _walk(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from _walk(child)
    elif isinstance(node, str):
        candidate = node.strip()
        if candidate.startswith("[") and candidate.endswith("]"):
            try:
                decoded = json.loads(candidate)
            except json.JSONDecodeError:
                return
            yield from _walk(decoded)


def _parse_offer_candidate(node: list[Any], currency: str) -> FlightOffer | None:
    if len(node) < 2:
        return None
    itinerary = node[0]
    price_block = node[1]
    if not isinstance(itinerary, list) or not isinstance(price_block, list):
        return None
    if len(itinerary) < 10 or len(price_block) < 2:
        return None
    segments_container = itinerary[2]
    if not isinstance(segments_container, list) or not segments_container:
        return None
    first_segment = segments_container[0]
    if not isinstance(first_segment, list) or len(first_segment) < 12:
        return None
    if not isinstance(first_segment[3], str) or not isinstance(first_segment[6], str):
        return None

    segments = [
        _parse_segment(segment, itinerary)
        for segment in segments_container
        if isinstance(segment, list)
    ]
    segments = [segment for segment in segments if segment is not None]
    if not segments:
        return None

    price = _coerce_int(price_block[0][1]) if isinstance(price_block[0], list) and len(price_block[0]) > 1 else None
    booking_token = price_block[1] if isinstance(price_block[1], str) else None
    emissions = itinerary[22] if len(itinerary) > 22 and isinstance(itinerary[22], list) else None
    layovers = _parse_layovers(itinerary[13] if len(itinerary) > 13 else None)

    first_leg = segments[0]
    last_leg = segments[-1]

    return FlightOffer(
        origin_airport=_string_or_none(itinerary[3]),
        destination_airport=_string_or_none(itinerary[6]) or last_leg.destination_airport,
        departure_date=_date_part(first_leg.departure_time),
        arrival_date=_date_part(last_leg.arrival_time),
        departure_time=first_leg.departure_time,
        arrival_time=last_leg.arrival_time,
        duration_minutes=_coerce_int(itinerary[9]),
        stops=len(segments) - 1 if segments else None,
        price=price,
        currency=currency,
        airlines=_airlines_from_segments(segments),
        flight_numbers=[segment.flight_number for segment in segments if segment.flight_number],
        layovers=layovers,
        emissions_kg=_coerce_int(emissions[7] / 1000) if emissions and len(emissions) > 7 and isinstance(emissions[7], (int, float)) else None,
        emissions_delta_percent=_coerce_int(emissions[3]) if emissions and len(emissions) > 3 else None,
        booking_token=booking_token,
        is_best=_bool_or_none(node[3]) if len(node) > 3 else None,
        segments=segments,
    )


def _parse_segment(segment: list[Any], itinerary: list[Any]) -> FlightSegment | None:
    if len(segment) < 23:
        return None
    carrier = segment[22] if isinstance(segment[22], list) else []
    airline_code = carrier[0] if len(carrier) > 0 and isinstance(carrier[0], str) else None
    flight_number = carrier[1] if len(carrier) > 1 and isinstance(carrier[1], str) else None
    airline_name = carrier[3] if len(carrier) > 3 and isinstance(carrier[3], str) else None
    return FlightSegment(
        airline_code=airline_code,
        airline_name=airline_name,
        flight_number=flight_number,
        operating_airline=_string_or_none(segment[2]),
        origin_airport=_string_or_none(segment[3]),
        origin_name=_string_or_none(segment[4]),
        destination_airport=_string_or_none(segment[6]),
        destination_name=_string_or_none(segment[5]),
        departure_time=_format_time(segment[20], segment[8]),
        arrival_time=_format_time(segment[21], segment[10]),
        duration_minutes=_coerce_int(segment[11]),
        aircraft=_string_or_none(segment[17]),
    )


def _parse_layovers(raw_layovers: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_layovers, list):
        return []
    parsed: list[dict[str, Any]] = []
    for layover in raw_layovers:
        if not isinstance(layover, list) or len(layover) < 2:
            continue
        parsed.append(
            {
                "duration_minutes": _coerce_int(layover[0]),
                "airport_code": _string_or_none(layover[1]),
                "airport_name": _string_or_none(layover[4]) if len(layover) > 4 else None,
                "city": _string_or_none(layover[5]) if len(layover) > 5 else None,
            }
        )
    return parsed


def _airlines_from_segments(segments: list[FlightSegment]) -> list[str]:
    seen: list[str] = []
    for segment in segments:
        if segment.airline_name and segment.airline_name not in seen:
            seen.append(segment.airline_name)
    return seen


def _format_date(value: Any) -> str | None:
    if not isinstance(value, list) or len(value) < 3:
        return None
    year, month, day = value[:3]
    if not all(isinstance(part, int) for part in (year, month, day)):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _format_time(date_value: Any, time_value: Any) -> str | None:
    date_text = _format_date(date_value)
    if date_text is None or not isinstance(time_value, list) or not time_value:
        return None
    hour = 0 if time_value[0] is None else time_value[0]
    minute_source = time_value[1] if len(time_value) > 1 else 0
    minute = 0 if minute_source is None else minute_source
    if not isinstance(hour, int) or not isinstance(minute, int):
        return None
    return f"{date_text}T{hour:02d}:{minute:02d}:00"


def _date_part(timestamp: str | None) -> str | None:
    if timestamp is None or "T" not in timestamp:
        return None
    return timestamp.split("T", 1)[0]


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None
