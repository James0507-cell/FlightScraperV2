from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .database import persist_run
from .models import NetworkCapture, ScrapeRun


def make_run_dir(base_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = base_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def archive_capture(run_dir: Path, capture: NetworkCapture) -> None:
    write_json(run_dir / "capture.json", capture.to_dict())
    if capture.request_body is not None:
        write_text(run_dir / "request.txt", capture.request_body)
    write_text(run_dir / "response.txt", capture.response_body)


def archive_run(run_dir: Path, run: ScrapeRun) -> None:
    archive_capture(run_dir, run.capture)
    write_json(run_dir / "offers.json", {"offers": [offer.to_dict() for offer in run.offers]})
    write_json(run_dir / "run.json", run.to_dict())
    persist_run(run_dir.parent / "scraper.sqlite", run)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
