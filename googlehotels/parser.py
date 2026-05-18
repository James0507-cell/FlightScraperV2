from __future__ import annotations

import json

from .models import HotelOffer


XSSI_PREFIX = ")]}'"


def strip_xssi_prefix(payload: str) -> str:
    text = payload.lstrip()
    if text.startswith(XSSI_PREFIX):
        return text.split("\n", 1)[1] if "\n" in text else ""
    return payload


def parse_hotels_response(payload: str) -> list[HotelOffer]:
    """Starter parser for Google Hotels responses.

    This intentionally does very little until real response samples are captured.
    Replace this with property-specific parsing once the backend payload shape is known.
    """

    normalized = strip_xssi_prefix(payload).strip()
    if not normalized:
        return []
    try:
        json.loads(normalized)
    except json.JSONDecodeError:
        return []
    return []
