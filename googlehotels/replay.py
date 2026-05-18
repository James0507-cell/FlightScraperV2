from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import HotelQuery


@dataclass(slots=True)
class ReplayTemplate:
    raw_request_body: str

    def build_request_body(self, query: HotelQuery) -> str:
        raise NotImplementedError(
            "Implement Google Hotels replay body generation after capturing a real request template."
        )


def load_replay_template(path: str | Path) -> ReplayTemplate:
    return ReplayTemplate(raw_request_body=Path(path).read_text(encoding="utf-8"))
