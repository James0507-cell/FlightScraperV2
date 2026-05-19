from __future__ import annotations

import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs

from flightscraperv2.booking_replay import build_booking_request_body
from flightscraperv2.parser import extract_offers, extract_round_trip_offers


ARTIFACT_DIR = Path("artifacts/20260517T115223Z")
RESEARCH_DIR = Path("artifacts/research_multistep/20260519T122849")


class BookingReplayTests(unittest.TestCase):
    def test_build_booking_request_body_from_round_trip_offer(self) -> None:
        outbound_payload = (RESEARCH_DIR / "resp_00_GetShoppingResults.txt").read_text(encoding="utf-8")
        return_payload = (RESEARCH_DIR / "resp_01_GetShoppingResults.txt").read_text(encoding="utf-8")
        offer = extract_round_trip_offers(outbound_payload, return_payload)[0]

        body = build_booking_request_body(offer)
        params = parse_qs(body)
        outer = json.loads(params["f.req"][0])
        inner = json.loads(outer[1])
        legs = inner[1][13]

        self.assertEqual(inner[0][1], offer.booking_token)
        self.assertEqual(legs[0][0], [[["SFO", 0]]])
        self.assertEqual(legs[0][1], [[["LAX", 0]]])
        self.assertEqual(legs[0][6], "2026-06-01")
        self.assertEqual(legs[0][8], [["SFO", "2026-06-01", "LAX", None, "F9", "3308"]])
        self.assertEqual(legs[1][0], [[["LAX", 0]]])
        self.assertEqual(legs[1][1], [[["SFO", 0]]])
        self.assertEqual(legs[1][6], "2026-06-05")
        self.assertEqual(legs[1][8], [["LAX", "2026-06-05", "SFO", None, "F9", "4593"]])

    def test_build_booking_request_body_from_one_way_offer(self) -> None:
        payload = (ARTIFACT_DIR / "response.txt").read_text(encoding="utf-8")
        offer = extract_offers(payload)[0]

        body = build_booking_request_body(offer)
        params = parse_qs(body)
        outer = json.loads(params["f.req"][0])
        inner = json.loads(outer[1])
        legs = inner[1][13]

        self.assertEqual(len(legs), 1)
        self.assertEqual(inner[0][1], offer.booking_token)
        self.assertEqual(legs[0][0], [[["DVO", 0]]])
        self.assertEqual(legs[0][1], [[["MNL", 0]]])
        self.assertEqual(legs[0][6], "2026-07-02")
        self.assertEqual(legs[0][8], [["DVO", "2026-07-02", "MNL", None, "5J", "3952"]])


if __name__ == "__main__":
    unittest.main()
