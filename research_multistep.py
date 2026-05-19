from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from datetime import datetime, UTC
from playwright.async_api import async_playwright, Response, Page

RESEARCH_DIR = Path("artifacts/research_multistep")
SEARCH_URL_DIRECT = "https://www.google.com/travel/flights/search?q=flights+from+SFO+to+LAX+on+2026-06-01+returning+2026-06-05"

async def research_capture():
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    run_dir = RESEARCH_DIR / timestamp
    run_dir.mkdir()

    print(f"Starting research capture in {run_dir}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US",
            viewport={"width": 1280, "height": 1000},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        resp_count = 0
        async def handle_response(response: Response):
            nonlocal resp_count
            if "FlightsFrontendService" in response.url:
                try:
                    method = response.url.split("/")[-1].split("?")[0]
                    body = await response.text()
                    filename = f"resp_{resp_count:02d}_{method}.txt"
                    (run_dir / filename).write_text(body, encoding="utf-8")
                    print(f"  [Intercepted & Saved] {filename}")
                    resp_count += 1
                except Exception as e:
                    print(f"  [Error] Failed to save response: {e}")

        page.on("response", handle_response)

        print(f"Navigating to {SEARCH_URL_DIRECT}...")
        await page.goto(SEARCH_URL_DIRECT, wait_until="networkidle")
        await asyncio.sleep(5)
        
        # Handle Consent
        consent_button = page.locator("button:has-text('Accept all'), button:has-text('I agree')")
        if await consent_button.count() > 0:
            print("  [Consent] Clicking consent button...")
            await consent_button.first.click()
            await asyncio.sleep(5)

        # 2. Select Outbound Flight
        print("Selecting outbound flight...")
        selectors = [
            "li[role='listitem']",
            "button[aria-label*='Select flight']",
            "[aria-label^='Select flight']"
        ]
        
        target_flight = None
        for selector in selectors:
            locators = await page.locator(selector).all()
            for loc in locators:
                text = await loc.inner_text()
                aria = await loc.get_attribute("aria-label") or ""
                if "Select flight" in aria or any(kw in text for kw in ["SFO", "LAX"]):
                    target_flight = loc
                    break
            if target_flight: break
        
        if target_flight:
            await target_flight.evaluate("el => el.click()")
            print("  [Clicked] Outbound flight.")
        else:
            print("  [Error] No outbound flight found.")
            await browser.close()
            return

        await asyncio.sleep(10)

        # 3. Select Return Flight
        print("Selecting return flight...")
        target_return = None
        for selector in selectors:
            locators = await page.locator(selector).all()
            for loc in locators:
                text = await loc.inner_text()
                aria = await loc.get_attribute("aria-label") or ""
                if "Select flight" in aria or any(kw in text for kw in ["SFO", "LAX"]):
                    target_return = loc
                    break
            if target_return: break

        if target_return:
            await target_return.evaluate("el => el.click()")
            print("  [Clicked] Return flight.")
        else:
            print("  [Error] No return flight found.")
            await browser.close()
            return

        print("Waiting for booking options page...")
        await asyncio.sleep(20) 
        await page.screenshot(path=run_dir / "06_booking_options.png")

        await browser.close()
        print(f"Research capture complete. Total responses saved: {resp_count}")

if __name__ == "__main__":
    asyncio.run(research_capture())
