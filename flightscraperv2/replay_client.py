from __future__ import annotations

import asyncio
from pathlib import Path
from time import perf_counter
from typing import Iterable

from playwright.async_api import Browser, BrowserContext, Playwright, Response, TimeoutError, async_playwright

from .google_flights import GoogleFlightsScraper, SEARCH_URL
from .models import FlightQuery, NetworkCapture, ScrapeRun
from .parser import extract_offers
from .replay import ReplayTemplate, load_replay_template_from_body
from .storage import archive_run, make_run_dir


class GoogleFlightsReplayClient:
    def __init__(self, headless: bool = True, archive_root: str = "artifacts") -> None:
        self._headless = headless
        self._archive_root = Path(archive_root)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._request_url: str | None = None
        self._template: ReplayTemplate | None = None
        self._bootstrap_lock = asyncio.Lock()

    async def __aenter__(self) -> "GoogleFlightsReplayClient":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._context = await self._browser.new_context(locale="en-US", timezone_id="Asia/Manila")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def bootstrap(self, query: FlightQuery) -> ScrapeRun:
        if self._context is None:
            raise RuntimeError("Replay client must be used as an async context manager.")

        async with self._bootstrap_lock:
            if self._request_url is not None and self._template is not None:
                return ScrapeRun(
                    query=query,
                    final_url=SEARCH_URL,
                    capture=NetworkCapture(url=self._request_url, request_body=None, response_body=""),
                    offers=[],
                    archive_dir=self._archive_root,
                    requested_mode="replay",
                    executed_mode="bootstrap_reused",
                    notes=["bootstrap already initialized"],
                )

            scraper = GoogleFlightsScraper(headless=self._headless, archive_root=str(self._archive_root))
            scraper._context = self._context
            run = await scraper.run_query(query)
            if not run.capture.request_body:
                raise RuntimeError("Bootstrap query did not capture a request body.")

            self._request_url = run.capture.url
            self._template = load_replay_template_from_body(run.capture.request_body)
            run.requested_mode = "replay"
            run.executed_mode = "browser_bootstrap"
            run.notes.append("browser bootstrap captured replay template")
            archive_run(run.archive_dir, run)
            return run

    async def replay_query(self, query: FlightQuery) -> ScrapeRun:
        if self._context is None:
            raise RuntimeError("Replay client must be used as an async context manager.")
        if self._request_url is None or self._template is None:
            raise RuntimeError("Replay client must be bootstrapped before replay queries.")

        last_error: Exception | None = None
        for attempt in range(1, query.max_retries + 1):
            try:
                started_at = perf_counter()
                request_body = self._template.build_request_body(query)
                request_started_at = perf_counter()
                response = await self._context.request.post(
                    self._request_url,
                    data=request_body,
                    headers={
                        "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
                        "origin": "https://www.google.com",
                        "referer": SEARCH_URL,
                    },
                    fail_on_status_code=False,
                )
                response_received_at = perf_counter()
                capture = await _capture_response(response, request_body=request_body)
                offers = extract_offers(capture.response_body)
                parsed_at = perf_counter()
                run_dir = make_run_dir(self._archive_root)
                run = ScrapeRun(
                    query=query,
                    final_url=SEARCH_URL,
                    capture=capture,
                    offers=offers,
                    archive_dir=run_dir,
                    requested_mode="replay",
                    executed_mode="replay",
                    timings={
                        "total_seconds": round(parsed_at - started_at, 4),
                        "request_seconds": round(response_received_at - request_started_at, 4),
                        "parse_seconds": round(parsed_at - response_received_at, 4),
                    },
                )
                archive_run(run_dir, run)
                archived_at = perf_counter()
                run.timings["archive_seconds"] = round(archived_at - parsed_at, 4)
                run.timings["total_seconds"] = round(archived_at - started_at, 4)
                archive_run(run_dir, run)
                return run
            except Exception as exc:
                last_error = exc
                if attempt >= query.max_retries:
                    break

        raise RuntimeError(
            f"Failed to replay Google Flights results after {query.max_retries} attempts."
        ) from last_error

    async def run_query_with_fallback(self, query: FlightQuery) -> ScrapeRun:
        bootstrap_notes: list[str] = []
        if self._request_url is None or self._template is None:
            try:
                bootstrap_run = await self.bootstrap(query)
                if bootstrap_run.offers:
                    return bootstrap_run
                bootstrap_notes.extend(bootstrap_run.notes)
            except Exception as exc:
                bootstrap_notes.append(f"bootstrap failed: {exc}")
                return await self._browser_fallback(query, bootstrap_notes)

        try:
            run = await self.replay_query(query)
            if bootstrap_notes:
                run.notes.extend(bootstrap_notes)
                archive_run(run.archive_dir, run)
            return run
        except Exception as exc:
            bootstrap_notes.append(f"replay failed: {exc}")
            return await self._browser_fallback(query, bootstrap_notes)

    async def replay_queries(
        self,
        queries: Iterable[FlightQuery],
        concurrency: int = 3,
    ) -> list[ScrapeRun]:
        semaphore = asyncio.Semaphore(concurrency)

        async def runner(query: FlightQuery) -> ScrapeRun:
            async with semaphore:
                return await self.run_query_with_fallback(query)

        return await asyncio.gather(*(runner(query) for query in queries))

    async def _browser_fallback(self, query: FlightQuery, notes: list[str]) -> ScrapeRun:
        scraper = GoogleFlightsScraper(headless=self._headless, archive_root=str(self._archive_root))
        scraper._context = self._context
        run = await scraper.run_query(query)
        run.requested_mode = "replay"
        run.executed_mode = "browser_fallback"
        run.notes.extend(notes)
        archive_run(run.archive_dir, run)
        return run


async def _capture_response(response: Response, request_body: str) -> NetworkCapture:
    response_body = await response.text()
    return NetworkCapture(
        url=response.url,
        request_body=request_body,
        response_body=response_body,
    )
