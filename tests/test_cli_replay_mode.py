from __future__ import annotations

import unittest

from flightscraperv2.cli import build_parser


class CliReplayModeTests(unittest.TestCase):
    def test_parser_accepts_replay_mode(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--mode",
                "replay",
                "--origin",
                "DVO",
                "--destination",
                "MNL",
                "--depart-date",
                "2026-07-02",
            ]
        )
        self.assertEqual(args.mode, "replay")

    def test_parser_accepts_detail_arguments(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--origin",
                "DVO",
                "--destination",
                "MNL",
                "--depart-date",
                "2026-07-02",
                "--detail-level",
                "complete",
                "--offer-index",
                "1",
                "--return-offer-index",
                "3",
            ]
        )
        self.assertEqual(args.detail_level, "complete")
        self.assertEqual(args.offer_index, 1)
        self.assertEqual(args.return_offer_index, 3)


if __name__ == "__main__":
    unittest.main()
