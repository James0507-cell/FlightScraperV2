from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs
import unittest

from flightscraperv2.models import FlightQuery
from flightscraperv2.replay import load_replay_template


ARTIFACT_DIR = Path("artifacts/20260517T115223Z")


class ReplayTemplateTests(unittest.TestCase):
    def test_build_request_body_from_archived_template(self) -> None:
        template = load_replay_template(ARTIFACT_DIR / "request.txt")
        body = template.build_request_body(
            FlightQuery(
                origin="CEB",
                destination="MNL",
                depart_date="2026-08-01",
                return_date="2026-08-10",
                trip_type="round_trip",
                passengers=2,
                max_stops=0,
            )
        )

        outer = json.loads(parse_qs(body.rstrip("&"))["f.req"][0])
        inner = json.loads(outer[1])
        legs = inner[1][13]

        self.assertEqual(legs[0][0][0][0][0], "CEB")
        self.assertEqual(legs[0][1][0][0][0], "MNL")
        self.assertEqual(legs[0][6], "2026-08-01")
        self.assertEqual(legs[1][0][0][0][0], "MNL")
        self.assertEqual(legs[1][1][0][0][0], "CEB")
        self.assertEqual(legs[1][6], "2026-08-10")
        self.assertEqual(inner[1][3], 1)
        self.assertEqual(inner[1][5], 2)

    def test_build_one_way_request_body(self) -> None:
        template = load_replay_template(ARTIFACT_DIR / "request.txt")
        body = template.build_request_body(
            FlightQuery(
                origin="DVO",
                destination="MNL",
                depart_date="2026-09-01",
                trip_type="one_way",
            )
        )

        outer = json.loads(parse_qs(body.rstrip("&"))["f.req"][0])
        inner = json.loads(outer[1])
        legs = inner[1][13]

        self.assertEqual(len(legs), 1)
        self.assertEqual(legs[0][6], "2026-09-01")


if __name__ == "__main__":
    unittest.main()
