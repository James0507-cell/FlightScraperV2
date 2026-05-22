# Command Reference

This document contains the main commands for running the scraper, the API server, and the tests.

Run commands from the project root:

```powershell
C:\Users\Admin\PycharmProjects\FlightScraperV2
```

## Environment Setup

Install project dependencies into the local virtual environment:

```powershell
.\.venv\Scripts\python -m pip install -e .
```

Install the Chromium browser used by Playwright:

```powershell
.\.venv\Scripts\python -m playwright install chromium
```

## Offline Tests

Run the full unit test suite:

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```

## CLI Scraper

Run a one-way scrape in browser mode:

```powershell
.\.venv\Scripts\python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02
```

Default behavior:

- This now runs a fast `summary` scrape.
- It captures the initial `GetShoppingResults` payload only.
- It does not expand booking options for every offer.

Run a round-trip scrape in browser mode:

```powershell
.\.venv\Scripts\python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08
```

Run the old full expansion path explicitly:

```powershell
.\.venv\Scripts\python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --detail-level complete
```

Fetch booking options for one selected one-way offer:

```powershell
.\.venv\Scripts\python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --offer-index 0
```

Fetch return-flight choices for one selected round-trip outbound offer:

```powershell
.\.venv\Scripts\python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --offer-index 0
```

Fetch booking options for one specific round-trip combination:

```powershell
.\.venv\Scripts\python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --offer-index 0 --return-offer-index 0
```

Run replay mode:

```powershell
.\.venv\Scripts\python main.py --mode replay --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08
```

Run replay-first auto mode:

```powershell
.\.venv\Scripts\python main.py --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08
```

Run with a visible browser window:

```powershell
.\.venv\Scripts\python main.py --mode browser --headed --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08
```

Run a batch file:

```powershell
.\.venv\Scripts\python main.py --mode browser --query-file benchmark-queries.json --concurrency 1 --retries 2
```

Run the benchmark:

```powershell
.\.venv\Scripts\python main.py --benchmark --query-file benchmark-queries.json --concurrency 1 --retries 2
```

## CLI Reports

Show recent persisted runs:

```powershell
.\.venv\Scripts\python main.py --report recent-runs --limit 5
```

Show cheapest persisted offers for one route and date:

```powershell
.\.venv\Scripts\python main.py --report cheapest-offers --origin DVO --destination MNL --depart-date 2026-07-02 --limit 10
```

Show execution mode summary:

```powershell
.\.venv\Scripts\python main.py --report mode-summary
```

## API Server

Start the API server on `0.0.0.0:8000`:

```powershell
.\.venv\Scripts\python main_api.py
```

Equivalent `uvicorn` command:

```powershell
.\.venv\Scripts\python -m uvicorn flightscraperv2.api:app --host 0.0.0.0 --port 8000
```

If port `8000` is already occupied by another local process, stop that process or temporarily use a different port for local testing:

```powershell
.\.venv\Scripts\python -m uvicorn flightscraperv2.api:app --host 0.0.0.0 --port 8001
```

## Session-Based API (Recommended for Interactive Apps)

The session-based API is designed for trip planning applications where users search once and then browse multiple flight details without re-searching.

Create a search session:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/sessions -ContentType 'application/json' -Body '{"origin":"DVO","destination":"MNL","depart_date":"2026-07-02","return_date":"2026-07-08"}'
```

List active sessions:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/sessions
```

Get session details:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/sessions/{session_id}
```

Get offer details via session:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/sessions/{session_id}/details -ContentType 'application/json' -Body '{"offer_index":0}'
```

Get return flight options (round-trip):

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/sessions/{session_id}/details -ContentType 'application/json' -Body '{"offer_index":0}'
```

Get booking options (round-trip with return selected):

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/sessions/{session_id}/details -ContentType 'application/json' -Body '{"offer_index":0,"return_offer_index":0}'
```

Delete session (cleanup):

```powershell
Invoke-RestMethod -Method Delete http://127.0.0.1:8000/api/v1/sessions/{session_id}
```

## API Smoke Tests

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

One-way scrape request:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/scrape -ContentType 'application/json' -Body '{"mode":"browser","origin":"DVO","destination":"MNL","depart_date":"2026-07-02","detail_level":"summary","headless":true}'
```

Round-trip scrape request:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/scrape -ContentType 'application/json' -Body '{"mode":"browser","origin":"DVO","destination":"MNL","depart_date":"2026-07-02","return_date":"2026-07-08","detail_level":"summary","headless":true}'
```

Offer-details request (legacy):

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/scrape/details -ContentType 'application/json' -Body '{"origin":"DVO","destination":"MNL","depart_date":"2026-07-02","offer_index":0,"headless":true}'
```

Recent runs:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/reports/recent-runs?limit=3"
```

Cheapest offers:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/reports/cheapest-offers?origin=DVO&destination=MNL&depart_date=2026-07-02&limit=3"
```

Mode summary:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/reports/mode-summary"
```

## Useful Files

Main outputs from a successful scrape:

- `artifacts\<run-id>\capture.json`
- `artifacts\<run-id>\request.txt`
- `artifacts\<run-id>\response.txt`
- `artifacts\<run-id>\offers.json`
- `artifacts\<run-id>\run.json`

SQLite database:

- `artifacts\scraper.sqlite`

API reference:

- `docs\api-reference.md`
