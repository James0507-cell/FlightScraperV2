from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.parse import urlparse
from typing import Any

from .models import BookingOption, FlightOffer, FlightSegment

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


def extract_round_trip_offers(
    outbound_payload: str,
    return_payload: str,
    currency: str = "PHP",
) -> list[FlightOffer]:
    outbound_offers = extract_offers(outbound_payload, currency=currency)
    return_offers = extract_offers(return_payload, currency=currency)
    if not outbound_offers:
        return []
    selected_outbound = outbound_offers[0]
    return [
        _combine_round_trip_offer(selected_outbound, return_offer)
        for return_offer in return_offers
    ]


def extract_booking_options(payload: str, currency: str = "PHP") -> list[BookingOption]:
    parsed_lines = parse_google_payload(payload)
    if len(parsed_lines) < 2:
        return []
    root = parsed_lines[1]
    if (
        not isinstance(root, list)
        or not root
        or not isinstance(root[0], list)
        or len(root[0]) < 3
        or not isinstance(root[0][2], str)
    ):
        return []
    try:
        inner = json.loads(root[0][2])
    except json.JSONDecodeError:
        return []
    if (
        not isinstance(inner, list)
        or len(inner) < 2
        or not isinstance(inner[1], list)
        or not inner[1]
        or not isinstance(inner[1][0], list)
    ):
        return []
    options: list[BookingOption] = []
    for node in inner[1][0]:
        option = _parse_booking_option(node, currency=currency)
        if option is not None:
            options.append(option)
    return options


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


def _combine_round_trip_offer(outbound: FlightOffer, return_offer: FlightOffer) -> FlightOffer:
    return FlightOffer(
        origin_airport=outbound.origin_airport,
        destination_airport=outbound.destination_airport,
        departure_date=outbound.departure_date,
        arrival_date=outbound.arrival_date,
        departure_time=outbound.departure_time,
        arrival_time=outbound.arrival_time,
        duration_minutes=outbound.duration_minutes,
        stops=outbound.stops,
        price=return_offer.price if return_offer.price is not None else outbound.price,
        currency=return_offer.currency or outbound.currency,
        trip_type="round_trip",
        airlines=outbound.airlines,
        flight_numbers=outbound.flight_numbers,
        layovers=outbound.layovers,
        emissions_kg=outbound.emissions_kg,
        emissions_delta_percent=outbound.emissions_delta_percent,
        booking_token=return_offer.booking_token or outbound.booking_token,
        is_best=return_offer.is_best if return_offer.is_best is not None else outbound.is_best,
        segments=outbound.segments,
        return_origin_airport=return_offer.origin_airport,
        return_destination_airport=return_offer.destination_airport,
        return_departure_date=return_offer.departure_date,
        return_arrival_date=return_offer.arrival_date,
        return_departure_time=return_offer.departure_time,
        return_arrival_time=return_offer.arrival_time,
        return_duration_minutes=return_offer.duration_minutes,
        return_stops=return_offer.stops,
        return_airlines=return_offer.airlines,
        return_flight_numbers=return_offer.flight_numbers,
        return_layovers=return_offer.layovers,
        return_segments=return_offer.segments,
    )


def _parse_booking_option(node: Any, currency: str) -> BookingOption | None:
    if not isinstance(node, list) or len(node) < 8:
        return None

    provider = node[1][0] if isinstance(node[1], list) and node[1] else None
    provider_code = provider[0] if isinstance(provider, list) and len(provider) > 0 and isinstance(provider[0], str) else None
    provider_name = provider[1] if isinstance(provider, list) and len(provider) > 1 and isinstance(provider[1], str) else None
    provider_domain = _extract_provider_domain(node[5] if len(node) > 5 else None)
    deeplink_url = _extract_deeplink(node[5] if len(node) > 5 else None)

    price_block = node[7] if len(node) > 7 and isinstance(node[7], list) else None
    price = None
    if price_block and isinstance(price_block[0], list) and len(price_block[0]) > 1:
        price = _coerce_int(price_block[0][1])

    fare_name = None
    if len(node) > 21 and isinstance(node[21], list) and len(node[21]) > 0:
        details = node[21]
        if isinstance(details[0], list) and len(details[0]) > 1 and isinstance(details[0][1], str):
            fare_name = details[0][1]

    flight_codes: list[str] = []
    if len(node) > 3 and isinstance(node[3], list):
        for pair in node[3]:
            if isinstance(pair, list) and len(pair) >= 2 and all(isinstance(item, str) for item in pair[:2]):
                flight_codes.append(f"{pair[0]} {pair[1]}")

    return BookingOption(
        provider_code=provider_code,
        provider_name=provider_name,
        provider_display_domain=provider_domain,
        provider_image_url=_build_provider_image_url(provider_domain),
        price=price,
        currency=currency,
        deeplink_url=deeplink_url,
        fare_name=fare_name,
        flight_codes=flight_codes,
        is_primary=_bool_or_none(node[24]) if len(node) > 24 else None,
        raw_rank=_coerce_int(node[0]) if len(node) > 0 else None,
    )


def _extract_provider_domain(node: Any) -> str | None:
    if not isinstance(node, list) or not node:
        return None
    value = node[0]
    if not isinstance(value, str):
        return None
    cleaned = value.replace("/...", "").strip()
    return cleaned or None


def _extract_deeplink(node: Any) -> str | None:
    if not isinstance(node, list) or len(node) < 3 or not isinstance(node[2], list):
        return None
    target = node[2]
    if len(target) < 2 or not isinstance(target[1], list):
        return None
    base_url = target[0] if isinstance(target[0], str) else None
    for pair in target[1]:
        if isinstance(pair, list) and len(pair) >= 2 and pair[0] == "u" and isinstance(pair[1], str):
            if not base_url:
                return pair[1]
            return f"{base_url}?{urlencode({'u': pair[1]})}"
    return None


def _build_provider_image_url(domain: str | None) -> str | None:
    if not domain:
        return None
    host = domain
    parsed = urlparse(domain if "://" in domain else f"https://{domain}")
    if parsed.netloc:
        host = parsed.netloc
    if not host:
        return None
    return f"https://www.google.com/s2/favicons?sz=64&domain_url=https://{host}/"


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
