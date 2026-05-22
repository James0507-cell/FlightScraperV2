from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter

from playwright.async_api import Browser, BrowserContext, Page, Response, TimeoutError, async_playwright

from .booking_links import resolve_google_deeplink
from .models import FlightOffer, FlightQuery, NetworkCapture, OfferDetails
from .parser import extract_booking_options, extract_offers, extract_round_trip_offers
from .storage import archive_offer_details, make_run_dir

logger = logging.getLogger("session")

SEARCH_URL = "https://www.google.com/travel/flights/search"

SESSION_TTL_SECONDS = 600


def _is_results_response(response: Response) -> bool:
    return "GetShoppingResults" in response.url and response.status == 200


def _is_booking_results_response(response: Response) -> bool:
    return "GetBookingResults" in response.url and response.status == 200


async def _capture_from_response(response: Response) -> NetworkCapture:
    request_body = response.request.post_data
    response_body = await response.text()
    return NetworkCapture(
        url=response.url,
        request_body=request_body,
        response_body=response_body,
    )


@dataclass
class SearchSession:
    session_id: str
    query: FlightQuery
    context: BrowserContext
    offers: list[FlightOffer]
    initial_capture: NetworkCapture
    archive_dir: Path
    created_at: datetime
    expires_at: datetime
    final_url: str = ""
    notes: list[str] = field(default_factory=list)

    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at

    def touch(self) -> None:
        self.expires_at = datetime.now(UTC) + timedelta(seconds=SESSION_TTL_SECONDS)

    def to_summary(self) -> dict:
        return {
            "session_id": self.session_id,
            "origin": self.query.origin,
            "destination": self.query.destination,
            "depart_date": self.query.depart_date,
            "return_date": self.query.return_date,
            "offer_count": len(self.offers),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired(),
        }


class SessionManager:
    def __init__(self, headless: bool = True, archive_root: str = "artifacts", session_ttl: int = SESSION_TTL_SECONDS) -> None:
        self._headless = headless
        self._archive_root = Path(archive_root)
        self._session_ttl = session_ttl
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._sessions: dict[str, SearchSession] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._context = await self._browser.new_context(locale="en-US", timezone_id="Asia/Manila")
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self._sessions.clear()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def create_session(self, query: FlightQuery) -> SearchSession:
        async with self._lock:
            if self._context is None:
                raise RuntimeError("Session manager not started. Call start() first.")

            page = await self._context.new_page()
            try:
                started_at = perf_counter()
                await page.goto(SEARCH_URL, wait_until="domcontentloaded")
                capture = await self._submit_query(page, query)
                offers = extract_offers(capture.response_body)
                finished_at = perf_counter()
                await page.close()

                now = datetime.now(UTC)
                session_id = uuid.uuid4().hex[:12]
                archive_dir = make_run_dir(self._archive_root)

                session = SearchSession(
                    session_id=session_id,
                    query=query,
                    context=self._context,
                    offers=offers,
                    initial_capture=capture,
                    archive_dir=archive_dir,
                    created_at=now,
                    expires_at=now + timedelta(seconds=self._session_ttl),
                    final_url=page.url,
                    notes=[f"session created in {finished_at - started_at:.2f}s"],
                )

                self._sessions[session_id] = session
                logger.info("Created session %s for %s->%s (%d offers)", session_id, query.origin, query.destination, len(offers))
                return session
            except Exception:
                await page.close()
                raise

    async def get_session(self, session_id: str) -> SearchSession | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.is_expired():
                await self._close_session(session_id)
                return None
            session.touch()
            return session

    async def get_offers(self, session_id: str) -> list[dict] | None:
        session = await self.get_session(session_id)
        if session is None:
            return None
        return [offer.to_dict() for offer in session.offers]

    async def get_offer_details(
        self,
        session_id: str,
        offer_index: int,
        return_offer_index: int | None = None,
    ) -> OfferDetails | None:
        session = await self.get_session(session_id)
        if session is None:
            return None

        # Create a fresh page in the shared context (cookies preserved)
        page = await session.context.new_page()
        try:
            return await self._fetch_offer_details(page, session, offer_index, return_offer_index)
        finally:
            await page.close()

    async def _fetch_offer_details(
        self,
        page: Page,
        session: SearchSession,
        offer_index: int,
        return_offer_index: int | None,
    ) -> OfferDetails:
        query = session.query
        offers = session.offers

        if offer_index < 0 or offer_index >= len(offers):
            raise ValueError(f"Offer index {offer_index} is out of range for {len(offers)} offers.")

        started_at = perf_counter()

        # Navigate to search and wait for results
        await page.goto(SEARCH_URL, wait_until="domcontentloaded")
        await self._submit_query(page, query)

        # Re-extract offers from the fresh page
        # (We use the stored offers for selection, but need the page for interaction)
        selected_offer = offers[offer_index]
        supplemental_captures: list[NetworkCapture] = []
        notes: list[str] = list(session.notes)
        return_offers: list[FlightOffer] = []
        selected_itinerary = None
        booking_options = []

        if query.trip_type == "round_trip" and query.return_date:
            try:
                async with page.expect_response(_is_results_response, timeout=query.timeout_seconds * 1000) as return_response_info:
                    await self._select_flight(page, offer_index)
                return_response = await return_response_info.value
                return_capture = await _capture_from_response(return_response)
                supplemental_captures.append(return_capture)
                return_offers = extract_offers(return_capture.response_body)
                notes.append("selected outbound offer expanded into return-flight choices")

                if return_offer_index is not None:
                    if return_offer_index < 0 or return_offer_index >= len(return_offers):
                        raise ValueError(f"Return offer index {return_offer_index} is out of range for {len(return_offers)} return offers.")
                    selected_return_offer = return_offers[return_offer_index]
                    try:
                        async with page.expect_response(
                            _is_booking_results_response,
                            timeout=query.timeout_seconds * 1000,
                        ) as booking_response_info:
                            await self._select_flight(page, return_offer_index)
                        booking_response = await booking_response_info.value
                        booking_capture = await _capture_from_response(booking_response)
                        supplemental_captures.append(booking_capture)
                        selected_itinerary = extract_round_trip_offers(
                            session.initial_capture.response_body,
                            return_capture.response_body,
                        )[return_offer_index]
                        booking_options = extract_booking_options(booking_capture.response_body)
                        self._resolve_booking_urls(booking_options)
                        selected_itinerary.booking_options = booking_options
                        notes.append(
                            f"selected return offer {return_offer_index} expanded into booking options"
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
                    await self._select_flight(page, offer_index)
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

        return OfferDetails(
            query=query,
            final_url=page.url,
            capture=session.initial_capture,
            archive_dir=run_dir,
            selected_offer_index=offer_index,
            selected_return_offer_index=return_offer_index,
            selected_outbound_offer=selected_offer,
            return_offers=return_offers,
            selected_itinerary=selected_itinerary,
            booking_options=booking_options,
            supplemental_captures=supplemental_captures,
            timings={
                "total_seconds": round(finished_at - started_at, 4),
                "session_age_seconds": round((datetime.now(UTC) - session.created_at).total_seconds(), 4),
            },
            notes=notes,
        )

    async def delete_session(self, session_id: str) -> bool:
        async with self._lock:
            return await self._close_session(session_id)

    async def list_sessions(self) -> list[dict]:
        async with self._lock:
            return [s.to_summary() for s in self._sessions.values() if not s.is_expired()]

    async def _close_session(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        logger.info("Closed session %s", session_id)
        return True

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(60)
                async with self._lock:
                    expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
                    for sid in expired:
                        await self._close_session(sid)
                    if expired:
                        logger.info("Cleaned up %d expired sessions", len(expired))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cleanup loop error: %s", e)

    async def _submit_query(self, page: Page, query: FlightQuery) -> NetworkCapture:
        from urllib.parse import quote_plus

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
            search_url = self._build_direct_search_url(query)
            async with page.expect_response(_is_results_response, timeout=query.timeout_seconds * 1000) as response_info:
                await page.goto(search_url, wait_until="domcontentloaded")
            response = await response_info.value
        if query.max_stops is not None:
            async with page.expect_response(_is_results_response, timeout=query.timeout_seconds * 1000) as filtered_response_info:
                await self._apply_stops_filter(page, query.max_stops)
            response = await filtered_response_info.value
        return await _capture_from_response(response)

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

    def _resolve_booking_urls(self, options: list) -> None:
        for option in options:
            option.resolved_booking_url = resolve_google_deeplink(option.deeplink_url)

    def _build_direct_search_url(self, query: FlightQuery) -> str:
        from urllib.parse import quote_plus
        parts = [f"flights from {query.origin} to {query.destination} on {query.depart_date}"]
        if query.return_date:
            parts.append(f"returning {query.return_date}")
        return f"{SEARCH_URL}?q={quote_plus(' '.join(parts))}"
