from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from .models import FlightQuery


@dataclass(slots=True)
class ReplayTemplate:
    payload: list

    def build_request_body(self, query: FlightQuery) -> str:
        payload = deepcopy(self.payload)
        config = payload[1]
        if not isinstance(config, list) or len(config) < 14:
            raise ValueError("Unexpected replay template structure.")

        legs = config[13]
        if not isinstance(legs, list) or not legs:
            raise ValueError("Replay template is missing trip legs.")

        legs[0] = _build_leg(
            origin=query.origin,
            destination=query.destination,
            travel_date=query.depart_date,
        )

        if query.trip_type == "round_trip" and query.return_date:
            if len(legs) < 2:
                legs.append(
                    _build_leg(
                        origin=query.destination,
                        destination=query.origin,
                        travel_date=query.return_date,
                    )
                )
            else:
                legs[1] = _build_leg(
                    origin=query.destination,
                    destination=query.origin,
                    travel_date=query.return_date,
                )
        else:
            del legs[1:]

        config[3] = _max_stops_flag(query.max_stops)
        config[5] = _passenger_count(query.passengers)
        config[16] = 1 if query.trip_type == "round_trip" and query.return_date else None

        inner = json.dumps(payload, separators=(",", ":"))
        outer = json.dumps([None, inner], separators=(",", ":"))
        return urlencode({"f.req": outer}) + "&"


def load_replay_template(path: str | Path) -> ReplayTemplate:
    body = Path(path).read_text(encoding="utf-8")
    return load_replay_template_from_body(body)


def load_replay_template_from_body(body: str) -> ReplayTemplate:
    body = body.rstrip("&")
    parsed = parse_qs(body, keep_blank_values=True)
    if "f.req" not in parsed:
        raise ValueError("Request body does not contain f.req.")
    outer = json.loads(parsed["f.req"][0])
    if not isinstance(outer, list) or len(outer) < 2 or not isinstance(outer[1], str):
        raise ValueError("Unexpected outer f.req structure.")
    payload = json.loads(outer[1])
    if not isinstance(payload, list):
        raise ValueError("Unexpected inner payload structure.")
    return ReplayTemplate(payload=payload)


def _build_leg(origin: str, destination: str, travel_date: str) -> list:
    return [
        [[ [origin, 0] ]],
        [[ [destination, 0] ]],
        None,
        1,
        None,
        None,
        travel_date,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        3,
    ]


def _passenger_count(passengers: int) -> int:
    return max(1, passengers)


def _max_stops_flag(max_stops: int | None) -> int | None:
    if max_stops is None:
        return None
    if max_stops <= 0:
        return 1
    if max_stops == 1:
        return 2
    return 3
