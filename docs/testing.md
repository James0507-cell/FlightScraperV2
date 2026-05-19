# Testing Guide

This document covers how to test the Google Flights scraper locally.

## Test Order

Use this order:

1. Run offline unit tests.
2. Run one live summary scrape.
3. Run one live detail scrape.
4. Run one live benchmark batch.
5. Run SQLite report commands.

This sequence verifies the codebase from lowest risk to highest risk.

## 1. Offline Unit Tests

Run:

```powershell
python -m unittest discover -s tests -v
```

What this verifies:

- parser behavior
- replay-template generation
- SQLite persistence
- SQLite reporting queries

Expected result:

- all tests should pass

Current test modules:

- `tests/test_parser.py`
- `tests/test_replay.py`
- `tests/test_database.py`
- `tests/test_reports.py`
- `tests/test_cli_replay_mode.py`

## 2. Live Single-Query Scrape

Run one real summary query:

```powershell
python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --detail-level summary --retries 1 --headed
```

What to check:

- the command returns JSON
- `offer_count` is greater than `0`
- `archive_dir` points to a new folder under `artifacts/`
- `requested_mode` and `executed_mode` are present
- summary notes explain whether booking options or return choices were intentionally skipped

Expected files in the artifact folder:

- `capture.json`
- `request.txt`
- `response.txt`
- `offers.json`
- `run.json`

If SQLite persistence is working, this command should also create:

- `artifacts/scraper.sqlite`

## 3. Live Offer-Details Test

Fetch booking options for one selected offer:

```powershell
python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --offer-index 0 --retries 1 --headed
```

Fetch return-flight choices for a selected round-trip outbound offer:

```powershell
python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --offer-index 0 --retries 1 --headed
```

What this verifies:

- the second-stage scrape works independently from summary mode
- booking-option expansion is isolated to one selected itinerary
- round-trip return choices are fetched only when explicitly requested

## 4. Live Browser-Only Full Expansion Test

If you want to validate the slower baseline path directly:

```powershell
python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --detail-level complete --retries 1 --headed
```

What this verifies:

- Playwright submission still works
- the old all-in-one booking-option expansion path still works when explicitly requested

## 5. Live Replay Test

If you want to validate the replay path directly:

```powershell
python main.py --mode replay --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 2
```

What this verifies:

- browser bootstrap works
- replay request generation works
- replay request submission works
- replay parsing still matches current Google responses

What to look for:

- `executed_mode` may be `browser_bootstrap`, `replay`, or `browser_fallback`

## 6. Batch Test

Run a multi-query batch:

```powershell
python main.py --query-file benchmark-queries.json --concurrency 1 --retries 2
```

What this verifies:

- batch orchestration works
- repeated runs archive correctly
- replay reuse works across multiple queries
- per-query success and failure reporting works

## 7. Benchmark Test

Compare browser mode and replay mode:

```powershell
python main.py --benchmark --query-file benchmark-queries.json --concurrency 1 --retries 2
```

What this verifies:

- benchmark harness works
- browser and replay wall times are recorded
- benchmark report output is saved

Files to inspect afterward:

- `docs/benchmark-latest.json`
- `artifacts/benchmarks/*.json`

Important interpretation:

- replay may be slower for one query because of bootstrap cost
- replay should become faster across multi-query batches

## 8. SQLite Report Tests

After at least one successful archived run, test the report commands.

Recent runs:

```powershell
python main.py --report recent-runs --limit 5
```

Cheapest offers for one route/date:

```powershell
python main.py --report cheapest-offers --origin DVO --destination MNL --depart-date 2026-07-02 --limit 10
```

Mode summary:

```powershell
python main.py --report mode-summary
```

What this verifies:

- the SQLite database exists
- persisted runs are readable
- persisted offers are queryable
- mode-level timing summaries work

## Failure Cases To Watch

Common failure categories:

- Playwright cannot load or interact with Google Flights
- Google returns no `GetShoppingResults` response
- Google returns a `GetShoppingResults` error payload instead of offers
- Google does not emit `GetBookingResults` for a selected offer before timeout
- Google changes the request or response format
- replay works for bootstrap but fails for follow-up requests
- no `artifacts/scraper.sqlite` exists yet when report commands are run

If a report command fails with a missing database message, run a successful live scrape first.

## Practical Validation Checklist

Use this short checklist for a normal validation pass:

1. `python -m unittest discover -s tests -v`
2. `python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --detail-level summary --retries 1 --headed`
3. `python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --offer-index 0 --retries 1 --headed`
4. `python main.py --benchmark --query-file benchmark-queries.json --concurrency 1 --retries 2`
5. `python main.py --report recent-runs --limit 5`

## Notes

- Live Google Flights behavior can be unstable across runs.
- Current live testing is more reliable in headed browser mode than headless mode on this machine.
- Retry counts matter for live validation.
- For meaningful replay-speed validation, prefer batch tests over one-off single queries.
