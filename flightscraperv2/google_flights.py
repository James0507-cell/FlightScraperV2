from __future__ import annotations

import asyncio
from pathlib import Path
from time import perf_counter
from typing import Iterable

from playwright.async_api import Browser, BrowserContext, Page, Playwright, Request, Response, TimeoutError, async_playwright

from .models import FlightQuery, NetworkCapture, ScrapeRun
from .parser import extract_offers
from .storage import archive_run, make_run_dir

SEARCH_URL = "https://www.google.com/travel/flights/search"


class GoogleFlightsScraper:
    def __init__(self, headless: bool = True, archive_root: str = "artifacts") -> None:
        self._headless = headless
        self._archive_root = Path(archive_root)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> "GoogleFlightsScraper":
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

    async def run_query(self, query: FlightQuery) -> ScrapeRun:
        if self._context is None:
            raise RuntimeError("Scraper must be used as an async context manager.")

        last_error: Exception | None = None
        for attempt in range(1, query.max_retries + 1):
            page = await self._context.new_page()
            try:
                started_at = perf_counter()
                await page.goto(SEARCH_URL, wait_until="domcontentloaded")
                submission_started_at = perf_counter()
                capture = await self._submit_query(page, query)
                capture_finished_at = perf_counter()
                offers = extract_offers(capture.response_body)
                parse_finished_at = perf_counter()
                run_dir = make_run_dir(self._archive_root)
                run = ScrapeRun(
                    query=query,
                    final_url=page.url,
                    capture=capture,
                    offers=offers,
                    archive_dir=run_dir,
                    requested_mode="browser",
                    executed_mode="browser",
                    timings={
                        "total_seconds": round(parse_finished_at - started_at, 4),
                        "submission_seconds": round(capture_finished_at - submission_started_at, 4),
                        "parse_seconds": round(parse_finished_at - capture_finished_at, 4),
                    },
                )
                archive_run(run_dir, run)
                archived_at = perf_counter()
                run.timings["archive_seconds"] = round(archived_at - parse_finished_at, 4)
                run.timings["total_seconds"] = round(archived_at - started_at, 4)
                archive_run(run_dir, run)
                return run
            except TimeoutError as exc:
                last_error = exc
                if attempt >= query.max_retries:
                    break
            except Exception as exc:
                last_error = exc
                if attempt >= query.max_retries:
                    break
            finally:
                await page.close()

        raise RuntimeError(
            f"Failed to fetch Google Flights results after {query.max_retries} attempts."
        ) from last_error

    async def run_queries(
        self,
        queries: Iterable[FlightQuery],
        concurrency: int = 3,
    ) -> list[ScrapeRun]:
        semaphore = asyncio.Semaphore(concurrency)

        async def runner(query: FlightQuery) -> ScrapeRun:
            async with semaphore:
                return await self.run_query(query)

        return await asyncio.gather(*(runner(query) for query in queries))

    async def _submit_query(self, page: Page, query: FlightQuery) -> NetworkCapture:
        await self._stabilize_shell(page)
        await self._set_trip_type(page, query.trip_type)
        await self._set_passengers(page, query.passengers)
        await self._set_cabin(page, query.cabin)
        await self._fill_airport(page, label="Where from?", value=query.origin)
        await self._fill_airport(page, label="Where to?", value=query.destination)
        await self._fill_date(page, label="Departure", value=query.depart_date)
        if query.trip_type == "round_trip" and query.return_date:
            await self._fill_date(page, label="Return", value=query.return_date)
        async with page.expect_response(_is_results_response, timeout=query.timeout_seconds * 1000) as first_response_info:
            await page.get_by_label("Explore destinations").click()
        response = await first_response_info.value
        if query.max_stops is not None:
            async with page.expect_response(_is_results_response, timeout=query.timeout_seconds * 1000) as filtered_response_info:
                await self._apply_stops_filter(page, query.max_stops)
            response = await filtered_response_info.value
        return await _capture_from_response(response)

    async def _set_trip_type(self, page: Page, trip_type: str) -> None:
        desired = {
            "round_trip": "Round trip",
            "one_way": "One way",
            "multi_city": "Multi-city",
        }[trip_type]
        trigger = page.get_by_role("combobox", name="Change ticket type.")
        try:
            await trigger.click()
        except TimeoutError:
            return
        option = page.get_by_role("option", name=desired, exact=True)
        await option.click()

    async def _set_passengers(self, page: Page, passengers: int) -> None:
        if passengers == 1:
            return
        trigger = page.get_by_label("passenger, change number of passengers.", exact=False)
        await trigger.click()
        increase = page.get_by_label("Add adult")
        for _ in range(passengers - 1):
            await increase.click()
        await page.get_by_text("Done", exact=True).click()

    async def _set_cabin(self, page: Page, cabin: str) -> None:
        desired = {
            "economy": "Economy",
            "premium_economy": "Premium economy",
            "business": "Business",
            "first": "First",
        }[cabin]
        trigger = page.get_by_role("combobox", name="Change seating class.")
        await trigger.click()
        await page.get_by_role("option", name=desired, exact=True).click()

    async def _fill_airport(self, page: Page, label: str, value: str) -> None:
        field = page.get_by_label(label, exact=False).first
        await field.click()
        await page.keyboard.press("ControlOrMeta+A")
        await page.keyboard.press("Backspace")
        await page.keyboard.type(value)
        option = page.get_by_role("option", name=value, exact=False).first
        await option.wait_for()
        await option.click()

    async def _fill_date(self, page: Page, label: str, value: str) -> None:
        field = page.get_by_label(label, exact=True).first
        await field.evaluate(
            """(element, nextValue) => {
                element.focus();
                element.value = nextValue;
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
            }""",
            value,
        )
        await field.press("Tab")

    async def _apply_stops_filter(self, page: Page, max_stops: int) -> None:
        await page.get_by_role("button", name="Stops", exact=False).click()
        if max_stops <= 0:
            await page.get_by_role("radio", name="Nonstop only").click()
        elif max_stops == 1:
            await page.get_by_role("radio", name="1 stop or fewer").click()
        else:
            await page.get_by_role("radio", name="2 stops or fewer").click()

    async def _stabilize_shell(self, page: Page) -> None:
        await page.wait_for_load_state("domcontentloaded")
        await page.get_by_label("Where from?", exact=False).first.wait_for()


async def _request_body(request: Request) -> str | None:
    return request.post_data


async def _capture_from_response(response: Response) -> NetworkCapture:
    request_body = await _request_body(response.request)
    response_body = await response.text()
    return NetworkCapture(
        url=response.url,
        request_body=request_body,
        response_body=response_body,
    )


def _is_results_response(response: Response) -> bool:
    return "GetShoppingResults" in response.url and response.status == 200


async def run_single_query(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str | None,
    passengers: int,
    cabin: str,
    max_stops: int | None,
    headless: bool,
    archive_root: str,
    max_retries: int,
) -> ScrapeRun:
    trip_type = "round_trip" if return_date else "one_way"
    query = FlightQuery(
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        return_date=return_date,
        trip_type=trip_type,
        passengers=passengers,
        cabin=cabin,
        max_stops=max_stops,
        max_retries=max_retries,
    )
    async with GoogleFlightsScraper(headless=headless, archive_root=archive_root) as scraper:
        return await scraper.run_query(query)
