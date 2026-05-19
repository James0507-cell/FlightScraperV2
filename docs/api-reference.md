# API Reference

This document describes the HTTP API exposed by `flightscraperv2.api:app`.

Default server binding:

- Host: `0.0.0.0`
- Port: `8000`

Interactive docs are available at:

- `http://<host>:8000/docs`

## General Notes

- All responses are JSON.
- CORS is enabled for all origins so a mobile client can call the API directly.
- `POST /api/v1/scrape` now defaults to a fast `summary` scrape.
- Summary mode captures the initial `GetShoppingResults` payload only.
- Offer-detail expansion is handled separately by `POST /api/v1/scrape/details`.
- `return_date` is optional. If it is present, the API treats the query as round-trip. If it is omitted, the API treats the query as one-way.

## `GET /`

Returns basic API metadata.

Arguments:

- none

Example request:

```http
GET /
```

Sample output:

```json
{
  "service": "FlightScraperV2 API",
  "version": "0.1.0",
  "docs_url": "/docs",
  "openapi_url": "/openapi.json"
}
```

Explanation:

- `service`: human-readable service name
- `version`: current API version string
- `docs_url`: Swagger UI path
- `openapi_url`: raw OpenAPI schema path

## `GET /health`

Returns a simple health response.

Arguments:

- none

Example request:

```http
GET /health
```

Sample output:

```json
{
  "status": "ok",
  "service": "FlightScraperV2 API"
}
```

Explanation:

- `status`: server health indicator
- `service`: human-readable service name

## `POST /api/v1/scrape`

Runs a live scrape and returns the persisted summary run payload.

Request body arguments:

- `mode`: `auto`, `browser`, or `replay`
  Explanation: `auto` means replay-first with browser fallback; `browser` forces Playwright UI/network capture; `replay` forces replay mode with browser bootstrap/fallback when needed.
- `origin`: airport or city code, for example `DVO`
  Explanation: source airport used in the query.
- `destination`: airport or city code, for example `MNL`
  Explanation: target airport used in the query.
- `depart_date`: `YYYY-MM-DD`
  Explanation: outbound date.
- `return_date`: `YYYY-MM-DD` or omitted
  Explanation: include this for round-trip searches.
- `passengers`: integer from `1` to `9`
  Explanation: adult passenger count.
- `cabin`: `economy`, `premium_economy`, `business`, or `first`
  Explanation: cabin class requested from Google Flights.
- `max_stops`: `0`, `1`, `2`, or omitted
  Explanation: optional stop filter.
- `retries`: integer from `1` to `5`
  Explanation: retry count for scraper attempts.
- `detail_level`: `summary` or `complete`
  Explanation: `summary` is the fast default and stops after the initial search payload. `complete` re-enables the old full expansion path that drills into booking options for every parsed offer.
- `archive_root`: path string
  Explanation: output root for artifacts and SQLite persistence. Default is `artifacts`.
- `headless`: boolean
  Explanation: `true` runs without a visible browser; `false` shows the Playwright browser window.

Example one-way request:

```json
{
  "mode": "browser",
  "origin": "DVO",
  "destination": "MNL",
  "depart_date": "2026-07-02",
  "detail_level": "summary",
  "headless": true
}
```

Example round-trip request:

```json
{
  "mode": "browser",
  "origin": "DVO",
  "destination": "MNL",
  "depart_date": "2026-07-02",
  "return_date": "2026-07-08",
  "detail_level": "summary",
  "headless": true
}
```

Sample output from a verified one-way summary run on `2026-05-20`:

```json
{
  "query": {
    "origin": "DVO",
    "destination": "MNL",
    "depart_date": "2026-07-02",
    "return_date": null,
    "trip_type": "one_way",
    "passengers": 1,
    "cabin": "economy",
    "max_stops": null,
    "timeout_seconds": 45.0,
    "max_retries": 1,
    "detail_level": "summary",
    "selected_offer_index": null,
    "selected_return_offer_index": null
  },
  "final_url": "https://www.google.com/travel/flights/search?...",
  "offer_count": 27,
  "archive_dir": "artifacts\\20260519T165012309450Z",
  "requested_mode": "browser",
  "executed_mode": "browser",
  "timings": {
    "submission_seconds": 34.9958,
    "archive_seconds": 0.0378,
    "total_seconds": 36.4099
  },
  "notes": [
    "summary mode skips booking-option expansion; fetch offer details for provider options"
  ],
  "offers": [
    {
      "origin_airport": "DVO",
      "destination_airport": "MNL",
      "departure_date": "2026-07-02",
      "departure_time": "2026-07-02T11:30:00",
      "arrival_time": "2026-07-02T13:35:00",
      "duration_minutes": 125,
      "stops": 0,
      "price": 3001,
      "currency": "PHP",
      "trip_type": "one_way",
      "airlines": [
        "Cebu Pacific"
      ],
      "flight_numbers": [
        "964"
      ],
      "booking_options": []
    }
  ]
}
```

Explanation:

- `query`: normalized request as stored by the scraper
- `final_url`: last Google Flights page reached by the browser flow
- `offer_count`: total parsed offers returned
- `archive_dir`: artifact directory containing raw request and response files
- `requested_mode`: requested mode from the client
- `executed_mode`: actual mode used after fallback logic
- `timings`: measured scraper timings in seconds
- `offers`: parsed itineraries
- `notes`: explains whether summary mode intentionally skipped return choices or booking options
- `booking_options`: empty in summary mode unless `detail_level=complete` is used

## `POST /api/v1/scrape/details`

Runs a second-stage scrape for one selected offer.

Use this endpoint after `POST /api/v1/scrape` when you need one of these:

- booking options for one selected one-way offer
- return-flight choices for one selected round-trip outbound offer
- booking options for one selected round-trip combination

Additional request body arguments:

- `offer_index`: zero-based offer index from the summary response
  Explanation: selects the outbound offer to expand.
- `return_offer_index`: optional zero-based return-offer index
  Explanation: when present on round-trip queries, selects one return option and fetches booking options for that combined itinerary.

Example one-way details request:

```json
{
  "origin": "DVO",
  "destination": "MNL",
  "depart_date": "2026-07-02",
  "offer_index": 0,
  "headless": true
}
```

Example round-trip return-choice request:

```json
{
  "origin": "DVO",
  "destination": "MNL",
  "depart_date": "2026-07-02",
  "return_date": "2026-07-08",
  "offer_index": 0,
  "headless": true
}
```

Key response fields:

- `selected_outbound_offer`: the chosen outbound offer
- `return_offers`: populated when a round-trip outbound offer is expanded
- `selected_itinerary`: populated when a final itinerary is known
- `booking_options`: populated when Google emitted `GetBookingResults`
- `return_offer_count`: convenience count for `return_offers`
- `booking_option_count`: convenience count for `booking_options`

## `GET /api/v1/reports/recent-runs`

Returns recently persisted runs from `artifacts/scraper.sqlite` or another configured database path.

Query arguments:

- `limit`: integer from `1` to `100`
  Explanation: maximum number of rows to return.
- `archive_root`: path string, default `artifacts`
  Explanation: used to derive the default SQLite file path.
- `db_path`: optional explicit SQLite path
  Explanation: overrides `archive_root`.

Example request:

```http
GET /api/v1/reports/recent-runs?limit=3
```

Sample output:

```json
{
  "report": "recent-runs",
  "db_path": "artifacts\\scraper.sqlite",
  "limit": 3,
  "rows": [
    {
      "run_key": "artifacts\\20260519T153542172760Z",
      "archive_dir": "artifacts\\20260519T153542172760Z",
      "requested_mode": "browser",
      "executed_mode": "browser",
      "origin": "DVO",
      "destination": "MNL",
      "depart_date": "2026-07-02",
      "return_date": null,
      "captured_at": "2026-05-19T15:33:16+00:00",
      "offer_count": 27,
      "timings": {
        "archive_seconds": 0.1626,
        "parse_seconds": 0.0,
        "submission_seconds": 148.1724,
        "total_seconds": 149.1485
      },
      "notes": []
    }
  ]
}
```

Explanation:

- each row is one persisted scrape run
- `offer_count` is the number of offers parsed in that run
- `timings` are the stored per-run measurements

## `GET /api/v1/reports/cheapest-offers`

Returns the cheapest persisted offers, optionally filtered by route and date.

Query arguments:

- `limit`: integer from `1` to `100`
  Explanation: maximum rows returned.
- `origin`: optional airport code
  Explanation: filter by the query origin stored with the run.
- `destination`: optional airport code
  Explanation: filter by the query destination stored with the run.
- `depart_date`: optional `YYYY-MM-DD`
  Explanation: filter by the query departure date stored with the run.
- `archive_root`: path string, default `artifacts`
  Explanation: used to derive the default SQLite file path.
- `db_path`: optional explicit SQLite path
  Explanation: overrides `archive_root`.

Example request:

```http
GET /api/v1/reports/cheapest-offers?origin=DVO&destination=MNL&depart_date=2026-07-02&limit=3
```

Sample output:

```json
{
  "report": "cheapest-offers",
  "db_path": "artifacts\\scraper.sqlite",
  "limit": 3,
  "filters": {
    "origin": "DVO",
    "destination": "MNL",
    "depart_date": "2026-07-02"
  },
  "rows": [
    {
      "run_key": "artifacts\\20260519T153542172760Z",
      "archive_dir": "artifacts\\20260519T153542172760Z",
      "executed_mode": "browser",
      "query": {
        "origin": "DVO",
        "destination": "MNL",
        "depart_date": "2026-07-02",
        "return_date": null
      },
      "captured_at": "2026-05-19T15:33:16+00:00",
      "offer_index": 0,
      "origin_airport": "DVO",
      "destination_airport": "MNL",
      "departure_date": "2026-07-02",
      "arrival_date": "2026-07-02",
      "departure_time": "2026-07-02T11:30:00",
      "arrival_time": "2026-07-02T13:35:00",
      "duration_minutes": 125,
      "stops": 0,
      "price": 3001,
      "currency": "PHP",
      "airlines": [
        "Cebu Pacific"
      ],
      "flight_numbers": [
        "964"
      ],
      "layovers": [],
      "emissions_kg": 72,
      "emissions_delta_percent": -29,
      "booking_token": "CjRIcXlzLXNGeW4taGdBRlZxWXdCRy0tLS0tLS0tLXNlb3gyNUFBQUFBR29NZ3J3R2dGay1BEgU1Sjk2NBoKCLkXEAAaA1BIUDgccP8l",
      "is_best": true
    }
  ]
}
```

Explanation:

- each row is one stored offer, not one run
- `offer_index` is the offer position inside the original run
- `booking_token` is Google’s internal token for later booking lookup or replay

## `GET /api/v1/reports/mode-summary`

Returns aggregate statistics grouped by `executed_mode`.

Query arguments:

- `archive_root`: path string, default `artifacts`
  Explanation: used to derive the default SQLite file path.
- `db_path`: optional explicit SQLite path
  Explanation: overrides `archive_root`.

Example request:

```http
GET /api/v1/reports/mode-summary
```

Sample output:

```json
{
  "report": "mode-summary",
  "db_path": "artifacts\\scraper.sqlite",
  "rows": [
    {
      "executed_mode": "browser",
      "run_count": 12,
      "avg_offer_count": 22.08,
      "avg_total_seconds": 31.6249,
      "min_total_seconds": 3.8347,
      "max_total_seconds": 149.1485
    },
    {
      "executed_mode": "browser_bootstrap",
      "run_count": 12,
      "avg_offer_count": 29.83,
      "avg_total_seconds": 5.7367,
      "min_total_seconds": 3.7936,
      "max_total_seconds": 8.542
    },
    {
      "executed_mode": "browser_fallback",
      "run_count": 2,
      "avg_offer_count": 26.0,
      "avg_total_seconds": 5.3487,
      "min_total_seconds": 4.0455,
      "max_total_seconds": 6.652
    }
  ]
}
```

Explanation:

- `executed_mode`: actual mode used by the scraper
- `run_count`: number of runs in that mode
- `avg_offer_count`: average offers parsed for that mode
- `avg_total_seconds`: average wall-clock time
- `min_total_seconds`: fastest recorded run
- `max_total_seconds`: slowest recorded run

## Verified Endpoint Test Runs

These endpoints were tested live on `2026-05-19`:

- `GET /`
- `GET /health`
- `POST /api/v1/scrape`
- `POST /api/v1/scrape/details`
- `GET /api/v1/reports/recent-runs`
- `GET /api/v1/reports/cheapest-offers`
- `GET /api/v1/reports/mode-summary`

Important note:

- The application is configured to run on `0.0.0.0:8000`.
- During verification, port `8000` on this machine was already occupied by another unrelated Python service, so the live endpoint checks were executed against the same API on port `8001`.
