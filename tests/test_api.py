from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from flightscraperv2.api import app
from flightscraperv2.models import FlightOffer, FlightQuery, NetworkCapture, ScrapeRun


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @patch("flightscraperv2.api.run_single", new_callable=AsyncMock)
    def test_scrape_endpoint(self, mock_run_single: AsyncMock) -> None:
        mock_run_single.return_value = ScrapeRun(
            query=FlightQuery(origin="DVO", destination="MNL", depart_date="2026-07-02", trip_type="one_way"),
            final_url="https://example.test/search",
            capture=NetworkCapture(url="https://example.test/api", request_body="f.req=test", response_body="[]"),
            offers=[
                FlightOffer(
                    origin_airport="DVO",
                    destination_airport="MNL",
                    departure_date="2026-07-02",
                    arrival_date="2026-07-02",
                    departure_time="2026-07-02T11:30:00",
                    arrival_time="2026-07-02T13:35:00",
                    duration_minutes=125,
                    stops=0,
                    price=3001,
                    currency="PHP",
                )
            ],
            archive_dir=Path("artifacts/test-run"),
        )
        response = self.client.post(
            "/api/v1/scrape",
            json={
                "origin": "DVO",
                "destination": "MNL",
                "depart_date": "2026-07-02",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["offer_count"], 1)
        self.assertEqual(payload["offers"][0]["price"], 3001)

    @patch("flightscraperv2.api.run_single", new_callable=AsyncMock)
    def test_scrape_details_endpoint(self, mock_run_single: AsyncMock) -> None:
        mock_run_single.return_value = type(
            "MockOfferDetails",
            (),
            {
                "return_offers": [],
                "booking_options": [],
                "to_dict": lambda self: {
                    "archive_dir": "artifacts/test-details",
                    "selected_offer_index": 2,
                    "return_offers": [],
                    "booking_options": [],
                },
            },
        )()
        response = self.client.post(
            "/api/v1/scrape/details",
            json={
                "origin": "DVO",
                "destination": "MNL",
                "depart_date": "2026-07-02",
                "offer_index": 2,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_offer_index"], 2)
        self.assertEqual(payload["return_offer_count"], 0)
        self.assertEqual(payload["booking_option_count"], 0)

    def test_recent_runs_missing_db_returns_404(self) -> None:
        response = self.client.get("/api/v1/reports/recent-runs?archive_root=missing-artifacts")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
