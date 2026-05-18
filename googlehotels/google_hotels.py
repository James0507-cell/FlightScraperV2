from __future__ import annotations

from pathlib import Path
from time import perf_counter

from .models import HotelQuery, NetworkCapture, ScrapeRun
from .parser import parse_hotels_response
from .storage import archive_run, make_run_dir


class GoogleHotelsScraper:
    def __init__(self, headless: bool = True, archive_root: str = "artifacts_hotels") -> None:
        self.headless = headless
        self.archive_root = Path(archive_root)

    async def __aenter__(self) -> "GoogleHotelsScraper":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def run_query(self, query: HotelQuery) -> ScrapeRun:
        started = perf_counter()
        run_dir = make_run_dir(self.archive_root)
        capture = NetworkCapture(
            url="https://www.google.com/travel/hotels",
            request_body=None,
            response_body="",
        )
        run = ScrapeRun(
            query=query,
            final_url="https://www.google.com/travel/hotels",
            capture=capture,
            offers=parse_hotels_response(capture.response_body),
            archive_dir=run_dir,
            requested_mode="browser",
            executed_mode="browser",
            timings={"total_seconds": round(perf_counter() - started, 4)},
            notes=[
                "Scaffold only: implement Playwright navigation and real network capture for Google Hotels."
            ],
        )
        archive_run(run_dir, run)
        return run


async def run_single_query(
    destination: str,
    check_in: str,
    check_out: str,
    adults: int,
    children: int,
    rooms: int,
    currency: str | None,
    max_price: int | None,
    headless: bool,
    archive_root: str,
    max_retries: int,
) -> ScrapeRun:
    query = HotelQuery(
        destination=destination,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
        children=children,
        rooms=rooms,
        currency=currency,
        max_price=max_price,
        max_retries=max_retries,
    )
    async with GoogleHotelsScraper(headless=headless, archive_root=archive_root) as scraper:
        return await scraper.run_query(query)
