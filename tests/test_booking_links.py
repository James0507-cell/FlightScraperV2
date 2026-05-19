from __future__ import annotations

import unittest

from flightscraperv2.booking_links import _extract_target_url


class BookingLinkTests(unittest.TestCase):
    def test_extract_target_url_from_meta_refresh_html(self) -> None:
        html = (
            "<html><head>"
            "<meta content=\"0;url='https://www.example.com/book?x=1&amp;y=2'\" http-equiv=\"refresh\">"
            "</head></html>"
        )
        resolved = _extract_target_url(
            "https://www.google.com/travel/clk/f?u=token",
            "text/html; charset=utf-8",
            html,
        )
        self.assertEqual(resolved, "https://www.example.com/book?x=1&y=2")


if __name__ == "__main__":
    unittest.main()
