from __future__ import annotations

from .models import HotelQuery


class GoogleHotelsReplayClient:
    def __init__(self, headless: bool = True, archive_root: str = "artifacts_hotels") -> None:
        self.headless = headless
        self.archive_root = archive_root

    async def __aenter__(self) -> "GoogleHotelsReplayClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def run_query_with_fallback(self, query: HotelQuery):
        raise NotImplementedError(
            "Implement replay mode after Google Hotels browser capture and request-template decoding are working."
        )
