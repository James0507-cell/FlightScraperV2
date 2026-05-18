from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .google_hotels import GoogleHotelsScraper, run_single_query
from .models import HotelQuery
from .replay_client import GoogleHotelsReplayClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Google Hotels scraper scaffold")
    parser.add_argument("--mode", choices=["auto", "browser", "replay"], default="auto")
    parser.add_argument("--destination", help="Destination city, area, or property")
    parser.add_argument("--check-in", help="Check-in date in YYYY-MM-DD")
    parser.add_argument("--check-out", help="Check-out date in YYYY-MM-DD")
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--children", type=int, default=0)
    parser.add_argument("--rooms", type=int, default=1)
    parser.add_argument("--currency")
    parser.add_argument("--max-price", type=int)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--query-file", help="Path to a JSON file containing a list of hotel queries")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--archive-root", default="artifacts_hotels")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.query_file:
        payload = asyncio.run(
            run_batch(
                query_file=args.query_file,
                mode=args.mode,
                headless=not args.headed,
                archive_root=args.archive_root,
            )
        )
        print(json.dumps(payload, indent=2))
        return 0

    if not args.destination or not args.check_in or not args.check_out:
        raise SystemExit("--destination, --check-in, and --check-out are required unless --query-file is used.")

    run = asyncio.run(
        run_single(
            mode=args.mode,
            destination=args.destination,
            check_in=args.check_in,
            check_out=args.check_out,
            adults=args.adults,
            children=args.children,
            rooms=args.rooms,
            currency=args.currency,
            max_price=args.max_price,
            headless=not args.headed,
            archive_root=args.archive_root,
            max_retries=args.retries,
        )
    )
    print(
        json.dumps(
            {
                "final_url": run.final_url,
                "hotel_count": len(run.offers),
                "archive_dir": str(run.archive_dir),
                "requested_mode": run.requested_mode,
                "executed_mode": run.executed_mode,
                "timings": run.timings,
                "notes": run.notes,
                "offers": [offer.to_dict() for offer in run.offers[:10]],
            },
            indent=2,
        )
    )
    return 0


async def run_single(
    mode: str,
    destination: str,
    check_in: str,
    check_out: str,
    adults: int,
    children: int,
    rooms: int,
    currency: str | None,
    max_price: int | None,
    headless: bool,
    archive_root: str,
    max_retries: int,
):
    effective_mode = "replay" if mode == "auto" else mode
    if effective_mode == "browser":
        return await run_single_query(
            destination=destination,
            check_in=check_in,
            check_out=check_out,
            adults=adults,
            children=children,
            rooms=rooms,
            currency=currency,
            max_price=max_price,
            headless=headless,
            archive_root=archive_root,
            max_retries=max_retries,
        )

    query = HotelQuery(
        destination=destination,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
        children=children,
        rooms=rooms,
        currency=currency,
        max_price=max_price,
        max_retries=max_retries,
    )
    async with GoogleHotelsReplayClient(headless=headless, archive_root=archive_root) as client:
        return await client.run_query_with_fallback(query)


async def run_batch(
    query_file: str,
    mode: str,
    headless: bool,
    archive_root: str,
) -> dict:
    queries = _load_queries(query_file)
    if mode == "browser":
        async with GoogleHotelsScraper(headless=headless, archive_root=archive_root) as scraper:
            results = [await _run_one(scraper.run_query, query) for query in queries]
    else:
        async with GoogleHotelsReplayClient(headless=headless, archive_root=archive_root) as client:
            results = [await _run_one(client.run_query_with_fallback, query) for query in queries]
    return {
        "count": len(results),
        "success_count": sum(1 for item in results if item["status"] == "ok"),
        "failure_count": sum(1 for item in results if item["status"] == "error"),
        "results": results,
    }


async def _run_one(runner, query: HotelQuery) -> dict:
    try:
        run = await runner(query)
        return {
            "status": "ok",
            "query": {
                "destination": query.destination,
                "check_in": query.check_in,
                "check_out": query.check_out,
            },
            "hotel_count": len(run.offers),
            "archive_dir": str(run.archive_dir),
            "requested_mode": run.requested_mode,
            "executed_mode": run.executed_mode,
            "timings": run.timings,
            "notes": run.notes,
        }
    except Exception as exc:
        return {
            "status": "error",
            "query": {
                "destination": query.destination,
                "check_in": query.check_in,
                "check_out": query.check_out,
            },
            "error": str(exc),
        }


def _load_queries(query_file: str) -> list[HotelQuery]:
    raw_queries = json.loads(Path(query_file).read_text(encoding="utf-8"))
    return [
        HotelQuery(
            destination=item["destination"],
            check_in=item["check_in"],
            check_out=item["check_out"],
            adults=item.get("adults", 2),
            children=item.get("children", 0),
            rooms=item.get("rooms", 1),
            currency=item.get("currency"),
            max_price=item.get("max_price"),
            timeout_seconds=item.get("timeout_seconds", 45.0),
            max_retries=item.get("max_retries", 3),
        )
        for item in raw_queries
    ]
