from __future__ import annotations

from pathlib import Path
import unittest

from flightscraperv2.parser import extract_offers


ARTIFACT_DIR = Path("artifacts/20260517T115223Z")


class ParserTests(unittest.TestCase):
    def test_extract_offers_from_archived_payload(self) -> None:
        payload = (ARTIFACT_DIR / "response.txt").read_text(encoding="utf-8")
        offers = extract_offers(payload)

        self.assertEqual(len(offers), 25)
        first = offers[0]
        self.assertEqual(first.origin_airport, "DVO")
        self.assertEqual(first.destination_airport, "MNL")
        self.assertEqual(first.price, 6177)
        self.assertEqual(first.airlines, ["Cebu Pacific"])
        self.assertEqual(first.flight_numbers, ["3952"])
        self.assertEqual(first.departure_time, "2026-07-02T00:05:00")
        self.assertEqual(first.arrival_time, "2026-07-02T02:05:00")
        self.assertEqual(first.emissions_kg, 93)


if __name__ == "__main__":
    unittest.main()
