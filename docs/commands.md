# Command Reference

This document contains copy-paste commands for the Google Flights scraper.

Run commands from the project root:

```powershell
C:\Users\Admin\PycharmProjects\FlightScraperV2
```

## Offline Tests

Run the unit test suite:

```powershell
python -m unittest discover -s tests -v
```

## Browser Mode

Run one live query through the Playwright UI path:

```powershell
python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 2
```

Run browser mode with a visible browser window:

```powershell
python main.py --mode browser --headed --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 2
```

## Replay Mode

Run one live query through replay mode:

```powershell
python main.py --mode replay --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 2
```

Run replay mode with a visible browser window:

```powershell
python main.py --mode replay --headed --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 2
```

## Auto Mode

Run the default replay-first mode:

```powershell
python main.py --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 2
```

## One-Way Query

Run a one-way flight query:

```powershell
python main.py --mode browser --origin CEB --destination MNL --depart-date 2026-07-03 --max-stops 0 --retries 2
```

## Batch Query

Run a batch from a JSON query file:

```powershell
python main.py --query-file benchmark-queries.json --concurrency 1 --retries 2
```

Run a browser-only batch:

```powershell
python main.py --mode browser --query-file benchmark-queries.json --concurrency 1 --retries 2
```

Run a replay-oriented batch:

```powershell
python main.py --mode replay --query-file benchmark-queries.json --concurrency 1 --retries 2
```

## Benchmark

Compare browser mode and replay mode:

```powershell
python main.py --benchmark --query-file benchmark-queries.json --concurrency 1 --retries 2
```

The latest benchmark summary is written to:

```powershell
docs/benchmark-latest.json
```

## SQLite Reports

Show recent persisted runs:

```powershell
python main.py --report recent-runs --limit 5
```

Show cheapest stored offers for one route/date:

```powershell
python main.py --report cheapest-offers --origin DVO --destination MNL --depart-date 2026-07-02 --limit 10
```

Show execution-mode summary:

```powershell
python main.py --report mode-summary
```

If the report commands fail with a missing database error, run a successful live scrape first so `artifacts/scraper.sqlite` is created.

## Replay Request Body Generation

Generate a request body from an archived request template:

```powershell
python main.py --print-request-body --request-template artifacts\20260517T115223Z\request.txt --origin CEB --destination MNL --depart-date 2026-08-01 --return-date 2026-08-10 --max-stops 0
```

## Useful Output Files

Successful live runs create an artifact directory under `artifacts/`.

Important files inside a run directory:

- `capture.json`
- `request.txt`
- `response.txt`
- `offers.json`
- `run.json`

Benchmark reports are written under:

- `artifacts/benchmarks/`

SQLite persistence is stored at:

- `artifacts/scraper.sqlite`
