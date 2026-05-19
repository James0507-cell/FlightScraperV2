from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from .database import list_cheapest_offers, list_recent_runs, summarize_modes
from .google_flights import GoogleFlightsScraper, run_single_query
from .models import FlightQuery
from .replay_client import GoogleFlightsReplayClient
from .replay import load_replay_template


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Google Flights network-first scraper")
    parser.add_argument("--mode", choices=["auto", "browser", "replay"], default="auto")
    parser.add_argument("--origin", help="Origin city or airport code")
    parser.add_argument("--destination", help="Destination city or airport code")
    parser.add_argument("--depart-date", help="Departure date in YYYY-MM-DD")
    parser.add_argument("--return-date", help="Return date in YYYY-MM-DD")
    parser.add_argument("--passengers", type=int, default=1)
    parser.add_argument(
        "--cabin",
        choices=["economy", "premium_economy", "business", "first"],
        default="economy",
    )
    parser.add_argument("--max-stops", type=int, choices=[0, 1, 2])
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--detail-level", choices=["summary", "complete"], default="summary")
    parser.add_argument("--offer-index", type=int, help="Selected offer index for detail scraping")
    parser.add_argument("--return-offer-index", type=int, help="Selected return-offer index for round-trip detail scraping")
    parser.add_argument("--query-file", help="Path to a JSON file containing a list of queries")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--benchmark", action="store_true", help="Run browser and replay benchmarks for the given query file")
    parser.add_argument("--request-template", help="Path to an archived request.txt file used to build replay bodies")
    parser.add_argument("--print-request-body", action="store_true", help="Print a generated f.req body instead of running the scraper")
    parser.add_argument("--headed", action="store_true", help="Run the browser with a visible window")
    parser.add_argument("--archive-root", default="artifacts")
    parser.add_argument("--db-path", help="Path to the SQLite database. Defaults to <archive-root>/scraper.sqlite")
    parser.add_argument("--report", choices=["recent-runs", "cheapest-offers", "mode-summary"])
    parser.add_argument("--limit", type=int, default=10)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.report:
        payload = run_report(
            report_name=args.report,
            db_path=args.db_path or str(Path(args.archive_root) / "scraper.sqlite"),
            limit=args.limit,
            origin=args.origin,
            destination=args.destination,
            depart_date=args.depart_date,
        )
        print(json.dumps(payload, indent=2))
        return 0

    if args.print_request_body:
        if not args.request_template:
            raise SystemExit("--request-template is required with --print-request-body.")
        if not args.origin or not args.destination or not args.depart_date:
            raise SystemExit("--origin, --destination, and --depart-date are required with --print-request-body.")
        template = load_replay_template(args.request_template)
        query = FlightQuery(
            origin=args.origin,
            destination=args.destination,
            depart_date=args.depart_date,
            return_date=args.return_date,
            trip_type="round_trip" if args.return_date else "one_way",
            passengers=args.passengers,
            cabin=args.cabin,
            max_stops=args.max_stops,
            max_retries=args.retries,
        )
        print(template.build_request_body(query))
        return 0

    if args.benchmark:
        if not args.query_file:
            raise SystemExit("--query-file is required with --benchmark.")
        payload = asyncio.run(
            run_benchmark(
                query_file=args.query_file,
                headless=not args.headed,
                archive_root=args.archive_root,
                concurrency=args.concurrency,
                max_retries=args.retries,
            )
        )
        print(json.dumps(payload, indent=2))
        return 0

    if args.query_file:
        payload = asyncio.run(
            run_batch(
                query_file=args.query_file,
                mode=args.mode,
                headless=not args.headed,
                archive_root=args.archive_root,
                concurrency=args.concurrency,
                max_retries=args.retries,
            )
        )
        print(json.dumps(payload, indent=2))
        return 0

    if not args.origin or not args.destination or not args.depart_date:
        raise SystemExit("--origin, --destination, and --depart-date are required unless --query-file is used.")

    run = asyncio.run(
        run_single(
            mode=args.mode,
            origin=args.origin,
            destination=args.destination,
            depart_date=args.depart_date,
            return_date=args.return_date,
            passengers=args.passengers,
            cabin=args.cabin,
            max_stops=args.max_stops,
            headless=not args.headed,
            archive_root=args.archive_root,
            max_retries=args.retries,
            detail_level=args.detail_level,
            selected_offer_index=args.offer_index,
            selected_return_offer_index=args.return_offer_index,
        )
    )
    if hasattr(run, "offers"):
        print(
            json.dumps(
                {
                    "final_url": run.final_url,
                    "offer_count": len(run.offers),
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
    else:
        payload = run.to_dict()
        payload["return_offer_count"] = len(payload["return_offers"])
        payload["booking_option_count"] = len(payload["booking_options"])
        print(json.dumps(payload, indent=2))
    return 0


def run_report(
    report_name: str,
    db_path: str,
    limit: int,
    origin: str | None,
    destination: str | None,
    depart_date: str | None,
) -> dict:
    path = Path(db_path)
    if not path.exists():
        raise SystemExit(f"Database not found: {path}")

    if report_name == "recent-runs":
        rows = list_recent_runs(path, limit=limit)
        return {
            "report": report_name,
            "db_path": str(path),
            "limit": limit,
            "rows": rows,
        }

    if report_name == "cheapest-offers":
        rows = list_cheapest_offers(
            path,
            limit=limit,
            origin=origin,
            destination=destination,
            depart_date=depart_date,
        )
        return {
            "report": report_name,
            "db_path": str(path),
            "limit": limit,
            "filters": {
                "origin": origin,
                "destination": destination,
                "depart_date": depart_date,
            },
            "rows": rows,
        }

    rows = summarize_modes(path)
    return {
        "report": report_name,
        "db_path": str(path),
        "rows": rows,
    }


async def run_batch(
    query_file: str,
    mode: str,
    headless: bool,
    archive_root: str,
    concurrency: int,
    max_retries: int,
) -> dict:
    queries = _load_queries(query_file=query_file, max_retries=max_retries)
    if mode == "browser":
        async with GoogleFlightsScraper(headless=headless, archive_root=archive_root) as scraper:
            results = await _run_batch_with_concurrency(
                queries,
                concurrency=concurrency,
                runner=scraper.run_query,
            )
    else:
        if not queries:
            results = []
        else:
            async with GoogleFlightsReplayClient(headless=headless, archive_root=archive_root) as client:
                results = await _run_batch_with_concurrency(
                    queries,
                    concurrency=concurrency,
                    runner=client.run_query_with_fallback,
                )
    return {
        "count": len(results),
        "success_count": sum(1 for item in results if item["status"] == "ok"),
        "failure_count": sum(1 for item in results if item["status"] == "error"),
        "results": results,
    }


async def run_single(
    mode: str,
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str | None,
    passengers: int,
    cabin: str,
    max_stops: int | None,
    headless: bool,
    archive_root: str,
    max_retries: int,
    detail_level: str = "summary",
    selected_offer_index: int | None = None,
    selected_return_offer_index: int | None = None,
):
    if selected_offer_index is not None:
        async with GoogleFlightsScraper(headless=headless, archive_root=archive_root) as scraper:
            return await scraper.run_offer_details(
                FlightQuery(
                    origin=origin,
                    destination=destination,
                    depart_date=depart_date,
                    return_date=return_date,
                    trip_type="round_trip" if return_date else "one_way",
                    passengers=passengers,
                    cabin=cabin,
                    max_stops=max_stops,
                    max_retries=max_retries,
                    detail_level=detail_level,
                    selected_offer_index=selected_offer_index,
                    selected_return_offer_index=selected_return_offer_index,
                )
            )

    effective_mode = "replay" if mode == "auto" else mode
    if detail_level != "summary":
        effective_mode = "browser"
    if effective_mode == "browser":
        return await run_single_query(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            passengers=passengers,
            cabin=cabin,
            max_stops=max_stops,
            headless=headless,
            archive_root=archive_root,
            max_retries=max_retries,
            detail_level=detail_level,
        )

    query = FlightQuery(
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        return_date=return_date,
        trip_type="round_trip" if return_date else "one_way",
        passengers=passengers,
        cabin=cabin,
        max_stops=max_stops,
        max_retries=max_retries,
        detail_level=detail_level,
    )
    async with GoogleFlightsReplayClient(headless=headless, archive_root=archive_root) as client:
        return await client.run_query_with_fallback(query)


async def run_benchmark(
    query_file: str,
    headless: bool,
    archive_root: str,
    concurrency: int,
    max_retries: int,
) -> dict:
    browser_started = perf_counter()
    browser_result = await run_batch(
        query_file=query_file,
        mode="browser",
        headless=headless,
        archive_root=archive_root,
        concurrency=concurrency,
        max_retries=max_retries,
    )
    browser_finished = perf_counter()

    replay_started = perf_counter()
    replay_result = await run_batch(
        query_file=query_file,
        mode="replay",
        headless=headless,
        archive_root=archive_root,
        concurrency=concurrency,
        max_retries=max_retries,
    )
    replay_finished = perf_counter()

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "query_file": str(Path(query_file)),
        "concurrency": concurrency,
        "browser": {
            "wall_time_seconds": round(browser_finished - browser_started, 4),
            **browser_result,
        },
        "replay": {
            "wall_time_seconds": round(replay_finished - replay_started, 4),
            **replay_result,
        },
    }
    report["summary"] = _build_benchmark_summary(report)
    report_path = _write_benchmark_report(report=report, archive_root=archive_root)
    report["report_path"] = str(report_path)
    Path("docs").mkdir(exist_ok=True)
    Path("docs/benchmark-latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


async def _run_batch_with_concurrency(
    queries: list[FlightQuery],
    concurrency: int,
    runner,
) -> list[dict]:
    semaphore = asyncio.Semaphore(concurrency)

    async def wrapped(query: FlightQuery) -> dict:
        async with semaphore:
            try:
                run = await runner(query)
                return {
                    "status": "ok",
                    "query": {
                        "origin": query.origin,
                        "destination": query.destination,
                        "depart_date": query.depart_date,
                        "return_date": query.return_date,
                    },
                    "final_url": run.final_url,
                    "offer_count": len(run.offers),
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
                        "origin": query.origin,
                        "destination": query.destination,
                        "depart_date": query.depart_date,
                        "return_date": query.return_date,
                    },
                    "error": str(exc),
                }

    return await asyncio.gather(*(wrapped(query) for query in queries))


def _load_queries(query_file: str, max_retries: int) -> list[FlightQuery]:
    raw_queries = json.loads(Path(query_file).read_text(encoding="utf-8"))
    return [
        FlightQuery(
            origin=item["origin"],
            destination=item["destination"],
            depart_date=item["depart_date"],
            return_date=item.get("return_date"),
            trip_type="round_trip" if item.get("return_date") else "one_way",
            passengers=item.get("passengers", 1),
            cabin=item.get("cabin", "economy"),
            max_stops=item.get("max_stops"),
            timeout_seconds=item.get("timeout_seconds", 45.0),
            max_retries=item.get("max_retries", max_retries),
        )
        for item in raw_queries
    ]


def _build_benchmark_summary(report: dict) -> dict:
    browser = report["browser"]
    replay = report["replay"]
    return {
        "browser_success_count": browser["success_count"],
        "replay_success_count": replay["success_count"],
        "browser_failure_count": browser["failure_count"],
        "replay_failure_count": replay["failure_count"],
        "browser_wall_time_seconds": browser["wall_time_seconds"],
        "replay_wall_time_seconds": replay["wall_time_seconds"],
        "speedup_ratio": round(
            browser["wall_time_seconds"] / replay["wall_time_seconds"],
            4,
        )
        if replay["wall_time_seconds"] > 0
        else None,
    }


def _write_benchmark_report(report: dict, archive_root: str) -> Path:
    benchmark_dir = Path(archive_root) / "benchmarks"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = benchmark_dir / f"{stamp}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path
