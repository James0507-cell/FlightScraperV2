from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from flightscraperv2.cli import run_report
from flightscraperv2.database import list_cheapest_offers, list_recent_runs, summarize_modes
from flightscraperv2.models import FlightOffer, FlightQuery, FlightSegment, NetworkCapture, ScrapeRun
from flightscraperv2.storage import archive_run


class ReportQueriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base_dir = Path("tests/.tmp") / f"reports-{uuid.uuid4().hex}"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._archive_sample_runs()

    def tearDown(self) -> None:
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_list_recent_runs_returns_latest_first(self) -> None:
        rows = list_recent_runs(self.base_dir / "scraper.sqlite", limit=5)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["origin"], "CEB")
        self.assertEqual(rows[0]["executed_mode"], "browser")
        self.assertEqual(rows[1]["origin"], "DVO")

    def test_list_cheapest_offers_can_filter_by_route(self) -> None:
        rows = list_cheapest_offers(
            self.base_dir / "scraper.sqlite",
            limit=5,
            origin="DVO",
            destination="MNL",
            depart_date="2026-07-02",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price"], 6177)
        self.assertEqual(rows[0]["airlines"], ["Cebu Pacific"])

    def test_summarize_modes_groups_runs(self) -> None:
        rows = summarize_modes(self.base_dir / "scraper.sqlite")
        by_mode = {row["executed_mode"]: row for row in rows}
        self.assertEqual(by_mode["replay"]["run_count"], 1)
        self.assertEqual(by_mode["browser"]["run_count"], 1)
        self.assertAlmostEqual(by_mode["replay"]["avg_total_seconds"], 0.5)
        self.assertAlmostEqual(by_mode["browser"]["avg_total_seconds"], 1.2)

    def test_run_report_returns_expected_payload_shape(self) -> None:
        payload = run_report(
            report_name="cheapest-offers",
            db_path=str(self.base_dir / "scraper.sqlite"),
            limit=3,
            origin="CEB",
            destination="MNL",
            depart_date="2026-07-03",
        )
        self.assertEqual(payload["report"], "cheapest-offers")
        self.assertEqual(payload["filters"]["origin"], "CEB")
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["rows"][0]["price"], 7020)

    def _archive_sample_runs(self) -> None:
        archive_run(self.base_dir / "run-1", self._build_run(
            run_name="run-1",
            origin="DVO",
            destination="MNL",
            depart_date="2026-07-02",
            return_date="2026-07-08",
            captured_at="2026-05-17T12:00:00+00:00",
            price=6177,
            airline_name="Cebu Pacific",
            airline_code="5J",
            flight_number="3952",
            executed_mode="replay",
            total_seconds=0.5,
        ))
        archive_run(self.base_dir / "run-2", self._build_run(
            run_name="run-2",
            origin="CEB",
            destination="MNL",
            depart_date="2026-07-03",
            return_date=None,
            captured_at="2026-05-17T12:05:00+00:00",
            price=7020,
            airline_name="Philippine Airlines",
            airline_code="PR",
            flight_number="2842",
            executed_mode="browser",
            total_seconds=1.2,
        ))

    def _build_run(
        self,
        run_name: str,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
        captured_at: str,
        price: int,
        airline_name: str,
        airline_code: str,
        flight_number: str,
        executed_mode: str,
        total_seconds: float,
    ) -> ScrapeRun:
        run_dir = self.base_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        departure_time = f"{depart_date}T00:05:00"
        arrival_time = f"{depart_date}T02:05:00"
        return ScrapeRun(
            query=FlightQuery(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                return_date=return_date,
                trip_type="round_trip" if return_date else "one_way",
            ),
            final_url="https://www.google.com/travel/flights/search",
            capture=NetworkCapture(
                url="https://www.google.com/_/FlightsFrontendUi/data/travel.frontend.flights.FlightsFrontendService/GetShoppingResults",
                request_body="f.req=test&",
                response_body=")]}'\n[]",
                captured_at=captured_at,
            ),
            offers=[
                FlightOffer(
                    origin_airport=origin,
                    destination_airport=destination,
                    departure_date=depart_date,
                    arrival_date=depart_date,
                    departure_time=departure_time,
                    arrival_time=arrival_time,
                    duration_minutes=120,
                    stops=0,
                    price=price,
                    currency="PHP",
                    airlines=[airline_name],
                    flight_numbers=[flight_number],
                    emissions_kg=93,
                    emissions_delta_percent=-8,
                    booking_token=f"token-{run_name}",
                    is_best=True,
                    segments=[
                        FlightSegment(
                            airline_code=airline_code,
                            airline_name=airline_name,
                            flight_number=flight_number,
                            operating_airline=None,
                            origin_airport=origin,
                            origin_name=f"{origin} Airport",
                            destination_airport=destination,
                            destination_name=f"{destination} Airport",
                            departure_time=departure_time,
                            arrival_time=arrival_time,
                            duration_minutes=120,
                            aircraft="Airbus A321",
                        )
                    ],
                )
            ],
            archive_dir=run_dir,
            requested_mode=executed_mode,
            executed_mode=executed_mode,
            timings={"total_seconds": total_seconds},
            notes=[f"{executed_mode} run"],
        )


if __name__ == "__main__":
    unittest.main()
