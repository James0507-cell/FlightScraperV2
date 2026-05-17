# Testing Guide

This document covers how to test the Google Flights scraper locally.

## Test Order

Use this order:

1. Run offline unit tests.
2. Run one live single-query scrape.
3. Run one live benchmark batch.
4. Run SQLite report commands.

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

Run one real Google Flights query:

```powershell
python main.py --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 2
```

What to check:

- the command returns JSON
- `offer_count` is greater than `0`
- `archive_dir` points to a new folder under `artifacts/`
- `requested_mode` and `executed_mode` are present

Expected files in the artifact folder:

- `capture.json`
- `request.txt`
- `response.txt`
- `offers.json`
- `run.json`

If SQLite persistence is working, this command should also create:

- `artifacts/scraper.sqlite`

## 3. Live Browser-Only Test

If you want to validate the slower baseline path directly:

```powershell
python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 2
```

What this verifies:

- Playwright submission still works
- `GetShoppingResults` capture still works without replay

## 4. Live Replay Test

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

## 5. Batch Test

Run a multi-query batch:

```powershell
python main.py --query-file benchmark-queries.json --concurrency 1 --retries 2
```

What this verifies:

- batch orchestration works
- repeated runs archive correctly
- replay reuse works across multiple queries
- per-query success and failure reporting works

## 6. Benchmark Test

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

## 7. SQLite Report Tests

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
- Google changes the request or response format
- replay works for bootstrap but fails for follow-up requests
- no `artifacts/scraper.sqlite` exists yet when report commands are run

If a report command fails with a missing database message, run a successful live scrape first.

## Practical Validation Checklist

Use this short checklist for a normal validation pass:

1. `python -m unittest discover -s tests -v`
2. `python main.py --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 2`
3. `python main.py --benchmark --query-file benchmark-queries.json --concurrency 1 --retries 2`
4. `python main.py --report recent-runs --limit 5`

## Notes

- Live Google Flights behavior can be unstable across runs.
- Retry counts matter for live validation.
- For meaningful replay-speed validation, prefer batch tests over one-off single queries.
