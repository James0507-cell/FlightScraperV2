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


if __name__ == "__main__":
    unittest.main()
