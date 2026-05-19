from __future__ import annotations

from pathlib import Path
import unittest

from flightscraperv2.parser import extract_booking_options, extract_offers


ARTIFACT_DIR = Path("artifacts/20260517T115223Z")
RESEARCH_DIR = Path("artifacts/research_multistep/20260519T122849")


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

    def test_extract_round_trip_offers_from_archived_payloads(self) -> None:
        from flightscraperv2.parser import extract_round_trip_offers

        outbound_payload = (RESEARCH_DIR / "resp_00_GetShoppingResults.txt").read_text(encoding="utf-8")
        return_payload = (RESEARCH_DIR / "resp_01_GetShoppingResults.txt").read_text(encoding="utf-8")

        offers = extract_round_trip_offers(outbound_payload, return_payload)

        self.assertEqual(len(offers), 3)
        first = offers[0]
        self.assertEqual(first.trip_type, "round_trip")
        self.assertEqual(first.origin_airport, "SFO")
        self.assertEqual(first.destination_airport, "LAX")
        self.assertEqual(first.departure_time, "2026-06-01T15:21:00")
        self.assertEqual(first.return_origin_airport, "LAX")
        self.assertEqual(first.return_destination_airport, "SFO")
        self.assertEqual(first.return_departure_time, "2026-06-05T17:54:00")
        self.assertEqual(first.return_arrival_time, "2026-06-05T19:36:00")
        self.assertEqual(first.price, 7899)
        self.assertEqual(first.flight_numbers, ["3308"])
        self.assertEqual(first.return_flight_numbers, ["4593"])

    def test_extract_booking_options_from_archived_payload(self) -> None:
        payload = (RESEARCH_DIR / "resp_02_GetBookingResults.txt").read_text(encoding="utf-8")
        options = extract_booking_options(payload)

        self.assertEqual(len(options), 2)
        first = options[0]
        self.assertEqual(first.provider_name, "Frontier")
        self.assertEqual(first.provider_display_domain, "www.flyfrontier.com")
        self.assertEqual(first.price, 7899)
        self.assertEqual(first.fare_name, "Basic Fare")
        self.assertEqual(first.flight_codes, ["F9 3308", "F9 4593"])
        self.assertTrue(first.deeplink_url.startswith("https://www.google.com/travel/clk/f?u="))
        self.assertEqual(
            first.provider_image_url,
            "https://www.google.com/s2/favicons?sz=64&domain_url=https://www.flyfrontier.com/",
        )


if __name__ == "__main__":
    unittest.main()
