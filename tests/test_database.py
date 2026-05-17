from __future__ import annotations

import sqlite3
from pathlib import Path
import shutil
from contextlib import closing
import unittest
import uuid

from flightscraperv2.models import FlightOffer, FlightQuery, FlightSegment, NetworkCapture, ScrapeRun
from flightscraperv2.storage import archive_run


class DatabasePersistenceTests(unittest.TestCase):
    def test_archive_run_persists_sqlite_rows(self) -> None:
        base_dir = Path("tests/.tmp") / f"db-{uuid.uuid4().hex}"
        base_dir.mkdir(parents=True, exist_ok=True)
        try:
            run_dir = base_dir / "run-1"
            run_dir.mkdir()
            run = ScrapeRun(
                query=FlightQuery(
                    origin="DVO",
                    destination="MNL",
                    depart_date="2026-07-02",
                    return_date="2026-07-08",
                ),
                final_url="https://www.google.com/travel/flights/search",
                capture=NetworkCapture(
                    url="https://www.google.com/_/FlightsFrontendUi/data/travel.frontend.flights.FlightsFrontendService/GetShoppingResults",
                    request_body="f.req=test&",
                    response_body=")]}'\n[]",
                ),
                offers=[
                    FlightOffer(
                        origin_airport="DVO",
                        destination_airport="MNL",
                        departure_date="2026-07-02",
                        arrival_date="2026-07-02",
                        departure_time="2026-07-02T00:05:00",
                        arrival_time="2026-07-02T02:05:00",
                        duration_minutes=120,
                        stops=0,
                        price=6177,
                        currency="PHP",
                        airlines=["Cebu Pacific"],
                        flight_numbers=["3952"],
                        emissions_kg=93,
                        emissions_delta_percent=-8,
                        booking_token="token-1",
                        is_best=True,
                        segments=[
                            FlightSegment(
                                airline_code="5J",
                                airline_name="Cebu Pacific",
                                flight_number="3952",
                                operating_airline=None,
                                origin_airport="DVO",
                                origin_name="Davao International Airport",
                                destination_airport="MNL",
                                destination_name="Ninoy Aquino International Airport",
                                departure_time="2026-07-02T00:05:00",
                                arrival_time="2026-07-02T02:05:00",
                                duration_minutes=120,
                                aircraft="Airbus A321",
                            )
                        ],
                    )
                ],
                archive_dir=run_dir,
                requested_mode="replay",
                executed_mode="replay",
                timings={"total_seconds": 0.5},
                notes=["stored in sqlite"],
            )

            archive_run(run_dir, run)

            db_path = base_dir / "scraper.sqlite"
            self.assertTrue(db_path.exists())

            with closing(sqlite3.connect(db_path)) as connection:
                run_count = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                offer_count = connection.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
                segment_count = connection.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
                executed_mode = connection.execute("SELECT executed_mode FROM runs").fetchone()[0]

            self.assertEqual(run_count, 1)
            self.assertEqual(offer_count, 1)
            self.assertEqual(segment_count, 1)
            self.assertEqual(executed_mode, "replay")
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
