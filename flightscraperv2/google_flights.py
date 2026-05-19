from __future__ import annotations

import asyncio
import re
from pathlib import Path
from time import perf_counter
from typing import Iterable
from urllib.parse import quote_plus

from playwright.async_api import Browser, BrowserContext, Page, Playwright, Request, Response, TimeoutError, async_playwright

from .booking_links import resolve_google_deeplink
from .booking_replay import build_booking_request_body
from .models import FlightQuery, NetworkCapture, OfferDetails, ScrapeRun
from .parser import extract_booking_options, extract_offers, extract_round_trip_offers
from .storage import archive_offer_details, archive_run, make_run_dir

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
                if query.detail_level == "complete":
                    if query.trip_type == "round_trip" and query.return_date:
                        capture, supplemental_captures, offers = await self._submit_round_trip_query(page, query)
                    else:
                        capture = await self._submit_query(page, query)
                        offers = extract_offers(capture.response_body)
                        supplemental_captures = await self._submit_one_way_booking_query(
                            page,
                            query,
                            offers,
                        )
                else:
                    capture = await self._submit_query(page, query)
                    offers = extract_offers(capture.response_body)
                    supplemental_captures = []
                capture_finished_at = perf_counter()
                parse_finished_at = perf_counter()
                notes: list[str] = []
                if query.detail_level != "complete":
                    if query.trip_type == "round_trip" and query.return_date:
                        notes.append(
                            "summary mode returns outbound options only for round-trip searches; "
                            "fetch offer details to load return choices and booking options"
                        )
                    else:
                        notes.append(
                            "summary mode skips booking-option expansion; fetch offer details for provider options"
                        )
                run_dir = make_run_dir(self._archive_root)
                run = ScrapeRun(
                    query=query,
                    final_url=page.url,
                    capture=capture,
                    offers=offers,
                    archive_dir=run_dir,
                    supplemental_captures=supplemental_captures,
                    requested_mode="browser",
                    executed_mode="browser",
                    notes=notes,
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

    async def run_offer_details(self, query: FlightQuery) -> OfferDetails:
        if self._context is None:
            raise RuntimeError("Scraper must be used as an async context manager.")
        if query.selected_offer_index is None or query.selected_offer_index < 0:
            raise ValueError("selected_offer_index must be provided for offer detail scraping.")

        page = await self._context.new_page()
        try:
            started_at = perf_counter()
            await page.goto(SEARCH_URL, wait_until="domcontentloaded")
            capture = await self._submit_query(page, query)
            offers = extract_offers(capture.response_body)
            selected_offer = self._select_offer_from_list(offers, query.selected_offer_index)
            supplemental_captures: list[NetworkCapture] = []
            notes: list[str] = []
            return_offers: list = []
            selected_itinerary = None
            booking_options = []

            if query.trip_type == "round_trip" and query.return_date:
                try:
                    async with page.expect_response(_is_results_response, timeout=query.timeout_seconds * 1000) as return_response_info:
                        await self._select_flight(page, query.selected_offer_index)
                    return_response = await return_response_info.value
                    return_capture = await _capture_from_response(return_response)
                    supplemental_captures.append(return_capture)
                    return_offers = extract_offers(return_capture.response_body)
                    notes.append("selected outbound offer expanded into return-flight choices")

                    if query.selected_return_offer_index is not None:
                        selected_return_offer = self._select_offer_from_list(return_offers, query.selected_return_offer_index)
                        try:
                            async with page.expect_response(
                                _is_booking_results_response,
                                timeout=query.timeout_seconds * 1000,
                            ) as booking_response_info:
                                await self._select_flight(page, query.selected_return_offer_index)
                            booking_response = await booking_response_info.value
                            booking_capture = await _capture_from_response(booking_response)
                            supplemental_captures.append(booking_capture)
                            selected_itinerary = extract_round_trip_offers(
                                capture.response_body,
                                return_capture.response_body,
                            )[query.selected_return_offer_index]
                            booking_options = extract_booking_options(booking_capture.response_body)
                            self._resolve_booking_urls(booking_options)
                            selected_itinerary.booking_options = booking_options
                            notes.append(
                                f"selected return offer {query.selected_return_offer_index} expanded into booking options"
                            )
                            if selected_return_offer.booking_token and not selected_itinerary.booking_token:
                                selected_itinerary.booking_token = selected_return_offer.booking_token
                        except TimeoutError:
                            notes.append("selected return offer did not emit GetBookingResults before timeout")
                except TimeoutError:
                    notes.append("selected outbound offer did not emit return-flight results before timeout")
            else:
                selected_itinerary = selected_offer
                try:
                    async with page.expect_response(
                        _is_booking_results_response,
                        timeout=query.timeout_seconds * 1000,
                    ) as booking_response_info:
                        await self._select_flight(page, query.selected_offer_index)
                    booking_response = await booking_response_info.value
                    booking_capture = await _capture_from_response(booking_response)
                    supplemental_captures.append(booking_capture)
                    booking_options = extract_booking_options(booking_capture.response_body)
                    self._resolve_booking_urls(booking_options)
                    selected_offer.booking_options = booking_options
                    notes.append("selected offer expanded into booking options")
                except TimeoutError:
                    notes.append("selected offer did not emit GetBookingResults before timeout")

            finished_at = perf_counter()
            run_dir = make_run_dir(self._archive_root)
            details = OfferDetails(
                query=query,
                final_url=page.url,
                capture=capture,
                archive_dir=run_dir,
                selected_offer_index=query.selected_offer_index,
                selected_return_offer_index=query.selected_return_offer_index,
                selected_outbound_offer=selected_offer,
                return_offers=return_offers,
                selected_itinerary=selected_itinerary,
                booking_options=booking_options,
                supplemental_captures=supplemental_captures,
                timings={
                    "total_seconds": round(finished_at - started_at, 4),
                },
                notes=notes,
            )
            archive_offer_details(run_dir, details)
            return details
        finally:
            await page.close()

    async def _submit_query(self, page: Page, query: FlightQuery) -> NetworkCapture:
        try:
            await self._prepare_query(page, query)
        except TimeoutError:
            await page.goto(SEARCH_URL, wait_until="domcontentloaded")
            await self._prepare_query(page, query)
        try:
            async with page.expect_response(_is_results_response, timeout=query.timeout_seconds * 1000) as first_response_info:
                await page.get_by_label("Explore destinations").click()
            response = await first_response_info.value
        except TimeoutError:
            response = await self._submit_query_via_direct_url(page, query)
        if query.max_stops is not None:
            async with page.expect_response(_is_results_response, timeout=query.timeout_seconds * 1000) as filtered_response_info:
                await self._apply_stops_filter(page, query.max_stops)
            response = await filtered_response_info.value
        return await _capture_from_response(response)

    async def _submit_query_via_direct_url(self, page: Page, query: FlightQuery) -> Response:
        search_url = _build_direct_search_url(query)
        async with page.expect_response(_is_results_response, timeout=query.timeout_seconds * 1000) as response_info:
            await page.goto(search_url, wait_until="domcontentloaded")
        return await response_info.value

    async def _submit_round_trip_query(
        self,
        page: Page,
        query: FlightQuery,
    ) -> tuple[NetworkCapture, list[NetworkCapture], list]:
        outbound_capture = await self._submit_query(page, query)
        async with page.expect_response(_is_results_response, timeout=query.timeout_seconds * 1000) as return_response_info:
            await self._select_first_flight(page)
        return_response = await return_response_info.value
        return_capture = await _capture_from_response(return_response)
        offers = extract_round_trip_offers(
            outbound_capture.response_body,
            return_capture.response_body,
        )
        supplemental_captures = [return_capture]
        try:
            async with page.expect_response(_is_booking_results_response, timeout=query.timeout_seconds * 1000) as booking_response_info:
                await self._select_first_flight(page)
            booking_response = await booking_response_info.value
            booking_capture = await _capture_from_response(booking_response)
            supplemental_captures.append(booking_capture)
            if offers:
                offers[0].booking_options = extract_booking_options(booking_capture.response_body)
                self._resolve_booking_urls(offers[0].booking_options)
            supplemental_captures.extend(
                await self._replay_booking_captures(
                    booking_capture.url,
                    page.url,
                    offers[1:],
                )
            )
        except TimeoutError:
            pass

        return outbound_capture, supplemental_captures, offers

    async def _submit_one_way_booking_query(
        self,
        page: Page,
        query: FlightQuery,
        offers: list,
    ) -> list[NetworkCapture]:
        if not offers:
            return []
        try:
            async with page.expect_response(_is_booking_results_response, timeout=query.timeout_seconds * 1000) as booking_response_info:
                await self._select_first_flight(page)
            booking_response = await booking_response_info.value
            booking_capture = await _capture_from_response(booking_response)
            offers[0].booking_options = extract_booking_options(booking_capture.response_body)
            self._resolve_booking_urls(offers[0].booking_options)
            captures = [booking_capture]
            captures.extend(
                await self._replay_booking_captures(
                    booking_capture.url,
                    page.url,
                    offers[1:],
                )
            )
            return captures
        except TimeoutError:
            return []

    async def _replay_booking_captures(
        self,
        request_url: str,
        referer_url: str,
        offers: list,
    ) -> list[NetworkCapture]:
        if self._context is None:
            return []

        captures: list[NetworkCapture] = []
        for offer in offers:
            try:
                request_body = build_booking_request_body(offer)
                response = await self._context.request.post(
                    request_url,
                    data=request_body,
                    headers={
                        "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
                        "origin": "https://www.google.com",
                        "referer": referer_url,
                    },
                    fail_on_status_code=False,
                )
                capture = await _capture_api_response(response, request_body=request_body)
                capture_options = extract_booking_options(capture.response_body)
                if capture_options:
                    self._resolve_booking_urls(capture_options)
                    offer.booking_options = capture_options
                captures.append(capture)
            except Exception:
                continue
        return captures

    def _resolve_booking_urls(self, options: list) -> None:
        for option in options:
            option.resolved_booking_url = resolve_google_deeplink(option.deeplink_url)

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
        origin_field = page.get_by_label("Where from?", exact=False).first
        try:
            await origin_field.wait_for(timeout=15000)
            return
        except TimeoutError:
            pass
        explore_button = page.get_by_role("button", name="Explore destinations")
        await explore_button.wait_for(timeout=30000)
        await explore_button.click()
        await origin_field.wait_for(timeout=45000)

    async def _prepare_query(self, page: Page, query: FlightQuery) -> None:
        await self._stabilize_shell(page)
        await self._set_trip_type(page, query.trip_type)
        await self._set_passengers(page, query.passengers)
        await self._set_cabin(page, query.cabin)
        await self._fill_airport(page, label="Where from?", value=query.origin)
        await self._fill_airport(page, label="Where to?", value=query.destination)
        await self._fill_date(page, label="Departure", value=query.depart_date)
        if query.trip_type == "round_trip" and query.return_date:
            await self._fill_date(page, label="Return", value=query.return_date)

    def _select_offer_from_list(self, offers: list, index: int):
        if index < 0 or index >= len(offers):
            raise ValueError(f"Offer index {index} is out of range for {len(offers)} offers.")
        return offers[index]

    async def _select_flight(self, page: Page, index: int) -> None:
        result_link = page.get_by_role("link", name=re.compile(r"Select flight$")).nth(index)
        try:
            await result_link.wait_for(timeout=15000)
            try:
                await result_link.click()
            except TimeoutError:
                await result_link.evaluate("(element) => element.click()")
            return
        except TimeoutError:
            raise TimeoutError(f"Failed to locate selectable flight result at index {index}.")

    async def _select_first_flight(self, page: Page) -> None:
        await self._select_flight(page, 0)


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


async def _capture_api_response(response, request_body: str) -> NetworkCapture:
    response_body = await response.text()
    return NetworkCapture(
        url=response.url,
        request_body=request_body,
        response_body=response_body,
    )


def _is_results_response(response: Response) -> bool:
    return "GetShoppingResults" in response.url and response.status == 200


def _is_booking_results_response(response: Response) -> bool:
    return "GetBookingResults" in response.url and response.status == 200


def _build_direct_search_url(query: FlightQuery) -> str:
    parts = [f"flights from {query.origin} to {query.destination} on {query.depart_date}"]
    if query.return_date:
        parts.append(f"returning {query.return_date}")
    return f"{SEARCH_URL}?q={quote_plus(' '.join(parts))}"


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
    detail_level: str = "summary",
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
        detail_level=detail_level,
    )
    async with GoogleFlightsScraper(headless=headless, archive_root=archive_root) as scraper:
        return await scraper.run_query(query)
