# Progress Summary

## Current State (v0.2.0)

The project is a working Google Flights scraper built around `Playwright` and network interception instead of DOM scraping. It now includes a **session-based API** designed for interactive trip planning applications.

Implemented components:

- `main.py`
  - Entrypoint for the CLI.
- `flightscraperv2/cli.py`
  - Supports single-query execution.
  - Supports batch execution from a JSON query file.
  - Supports configurable retries and concurrency.
  - Supports SQLite-backed reports for recent runs, cheapest offers, and mode summaries.
- `flightscraperv2/google_flights.py`
  - Opens Google Flights directly at the search page.
  - Fills the route, date, cabin, passenger, and stops inputs.
  - Waits for the `GetShoppingResults` network response.
  - Retries failed runs.
  - Supports concurrent query execution through a shared scraper instance.
- `flightscraperv2/session_manager.py`
  - Manages browser sessions for interactive trip planning.
  - Creates sessions with initial search results.
  - Fetches offer details using shared browser context.
  - Automatic session expiry and cleanup.
  - Thread-safe session access with async locks.
- `flightscraperv2/parser.py`
  - Strips the XSSI prefix from Google responses.
  - Walks nested payloads, including embedded JSON strings.
  - Extracts normalized offer data from the captured response.
- `flightscraperv2/replay.py`
  - Loads archived `request.txt` captures as replay templates.
  - Rebuilds new `f.req` bodies from `FlightQuery` inputs.
  - Provides an offline foundation for a direct request replay path.
- `flightscraperv2/replay_client.py`
  - Boots a live browser session once.
  - Uses a real browser-submitted query to capture a fresh replay template and endpoint URL.
  - Replays subsequent queries directly through Playwright's request client using the shared browser context.
- `flightscraperv2/models.py`
  - Defines query, segment, offer, capture, and run models.
- `flightscraperv2/storage.py`
  - Archives raw requests, raw responses, normalized offers, and run metadata under `artifacts/`.
- `flightscraperv2/database.py`
  - Persists runs, offers, and segments into SQLite.
  - Uses the archive flow so successful runs are stored automatically.
  - Exposes read-side queries for reporting over persisted runs and offers.
- `flightscraperv2/api.py`
  - FastAPI HTTP API with session-based endpoints.
  - Legacy scrape endpoints for non-interactive use.
  - Report endpoints for querying persisted data.
  - CORS enabled for direct browser client access.
  - Automatic session lifecycle management.
- `tests/`
  - Contains offline parser and replay-template tests using archived artifacts.

## Verified Progress

The scraper has been validated against live Google Flights responses.

Verified outcomes:

- Successful live query submission against Google Flights.
- Successful capture of `GetShoppingResults`.
- Successful archival of raw request and response payloads.
- Successful parsing of a live response into normalized offers.
- Confirmed batch/concurrency scaffolding compiles and is wired into the CLI.
- Confirmed replay-template generation works offline from archived request captures.
- Confirmed parser and replay behavior through automated unit tests.
- Added a CLI replay mode that uses a bootstrap browser query and then replays requests through the session context.
- Added persistent SQLite storage for archived runs.
- Added a query/report layer on top of SQLite for inspecting stored runs without re-reading artifact files.
- Added session-based API for interactive trip planning applications.
- Verified session creation, detail fetching, and cleanup through live API tests.
- All 19 unit tests passing.

Example validated artifact directories:

- `artifacts/20260517T114524Z`
- `artifacts/20260517T115223Z`

The successful run in `artifacts/20260517T115223Z` produced `25` parsed offers.

Current automated tests:

- `test_parser.py`
- `test_replay.py`
- `test_database.py`
- `test_reports.py`
- `test_api.py`
- `test_booking_links.py`
- `test_booking_replay.py`
- `test_cli_replay_mode.py`

## What Has Been Solved

The following technical uncertainties are no longer blockers:

- Google Flights can be scraped more effectively from network responses than from result-card HTML.
- `GetShoppingResults` contains usable structured data.
- Google's payload is not a public clean REST API, but it is parseable enough for an internal scraper pipeline.
- The date fields can be handled without relying on fragile calendar clicks.
- A retry layer is required because Google Flights interactions are not consistently stable across runs.
- Archived request bodies can be decoded into a reusable internal template for replay experiments.
- Session-based API enables interactive trip planning without re-searching for each detail fetch.

## Known Limitations

The implementation is a production scaffold with interactive API support.

Current limitations:

- Query submission still depends on Playwright browser automation for each search.
- Some selectors are still tied to Google's current frontend structure and may need updates if the UI changes.
- The parser is heuristic and based on the currently observed payload structure.
- The benchmark harness exists, but it is still oriented toward JSON artifact output and not long-run operational reporting.
- There is no deduplication or queueing layer yet.
- The live replay execution path exists and has been validated on current benchmark routes, but it still needs broader route coverage.
- There is no anti-blocking strategy yet beyond retries.
- Session detail fetches still require ~30-40 seconds per request (browser interaction time).

## What Still Needs To Be Done

The main remaining work is to turn the current working scaffold into a faster and more durable scraping system.

Remaining tasks:

1. Harden query submission further.
   - Reduce sensitivity to UI changes.
   - Improve fallback behavior when fields or dialogs behave differently.

2. Validate and harden the direct request replay execution path.
   - Confirm replay success against live Google Flights sessions.
   - Compare replayed response quality with browser-submitted response quality.
   - Improve fallback behavior when replay fails.

3. Expand the benchmark and profiling layer.
   - Measure navigation time, query time, parse time, retry rate, and offer yield.
   - Compare browser-driven submission versus direct replay over larger route sets.

4. Improve parsing coverage.
   - Validate more routes, more airlines, one-way trips, round trips, and connecting itineraries.
   - Confirm edge cases such as overnight flights and incomplete time fields.

5. Add structured failure handling.
   - Detect empty responses, malformed payloads, unusual traffic behavior, and parsing regressions.
   - Store failure reasons in a machine-readable format.

6. Add batch orchestration features.
   - Better result aggregation.
   - Partial failure reporting.
   - Optional resume behavior for large runs.

7. Add deduplication and richer storage behavior.
   - Build deduplication rules for repeated captures and repeated itineraries.
   - Expand SQLite reporting further, or move to Postgres later if needed.

8. Expand tests.
   - Keep unit tests for parser and replay templates.
   - Add integration tests for the CLI and storage flow.
   - Add regression coverage for multiple artifact samples.
   - Add session-based API integration tests.

## What Should Be Done Next

The next best engineering step is to improve operational usefulness and then keep pushing on speed.

Recommended next step:

1. Add richer reporting and deduplication on top of SQLite.
   - Summarize cheapest fares by route over time.
   - Flag duplicate itineraries across repeated scrapes.
   - Make persisted benchmark and run history easier to inspect.

Why this is next:

- The scraper now persists enough data to support actual operational inspection.
- Reporting makes replay and browser benchmarking easier to evaluate over time.
- Deduplication is needed before larger batch schedules become useful.
- Replay speed improvements will be easier to measure once persisted history is queryable.

## Suggested Near-Term Roadmap

### Phase 1

- Stabilize the existing Playwright submission path further.
- Expand parser/replay test coverage from archived payloads.
- Expand failure logging, benchmarking output, and persisted run reporting.

### Phase 2

- Prototype direct request replay.
- Measure performance against the current browser-driven path.
- Promote replay to primary mode if stable enough.

### Phase 3

- Add durable storage.
- Add larger-batch orchestration.
- Add deduplication and resumable runs.

### Phase 4 (Completed)

- Session-based API for interactive trip planning applications.
- Client implementation guide with code examples.
- Updated API documentation.

## Suggested Commands

Single query:

```powershell
python main.py --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 3
```

Batch query:

```powershell
python main.py --query-file queries.json --concurrency 3 --retries 3
```

Recent persisted runs:

```powershell
python main.py --report recent-runs --limit 5
```

This requires an existing `artifacts/scraper.sqlite`, which is created automatically after the next archived scrape run.

Cheapest stored offers for one route/date:

```powershell
python main.py --report cheapest-offers --origin DVO --destination MNL --depart-date 2026-07-02 --limit 10
```

Mode summary from SQLite:

```powershell
python main.py --report mode-summary
```

## Summary

The scraper has moved from idea stage to working prototype with interactive API support.

Current position:

- Live query execution works.
- Network capture works.
- Archiving works.
- SQLite persistence now works automatically during archival.
- SQLite reporting now works directly from the CLI.
- Offer parsing works.
- Batch scaffolding exists.
- Replay request bodies can now be generated offline from archived captures.
- Offline parser and replay tests now pass.
- A replay CLI mode and replay client now exist, using one bootstrap browser query plus replayed follow-up requests.
- Benchmarking and persisted reporting are both available from the CLI.
- Session-based API enables interactive trip planning without re-searching.
- Client implementation guide with code examples is available.

Next priority:

- Add richer deduplication and historical analysis on top of the persisted offer database.
