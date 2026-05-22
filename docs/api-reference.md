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
- `POST /api/v1/scrape` defaults to a fast `summary` scrape.
- Summary mode captures the initial `GetShoppingResults` payload only.
- Offer-detail expansion is handled separately by `POST /api/v1/scrape/details`.
- `return_date` is optional. If it is present, the API treats the query as round-trip. If it is omitted, the API treats the query as one-way.
- **Session-based API** (`/api/v1/sessions`) is available for interactive trip planning applications.

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
  "version": "0.2.0",
  "docs_url": "/docs",
  "openapi_url": "/openapi.json"
}
```

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

## Session-Based Endpoints (Recommended for Interactive Apps)

The session-based API is designed for trip planning applications where users search once and then browse multiple flight details.

### `POST /api/v1/sessions`

Creates a search session. Runs the initial search and returns flight offers. The session is kept alive for subsequent detail requests.

Request body arguments:

- `origin`: airport or city code, for example `DVO`
- `destination`: airport or city code, for example `MNL`
- `depart_date`: `YYYY-MM-DD`
- `return_date`: `YYYY-MM-DD` or omitted (one-way if omitted)
- `passengers`: integer from `1` to `9` (default: `1`)
- `cabin`: `economy`, `premium_economy`, `business`, or `first` (default: `economy`)
- `max_stops`: `0`, `1`, `2`, or omitted
- `retries`: integer from `1` to `5` (default: `3`)
- `detail_level`: `summary` or `complete` (default: `summary`)
- `session_ttl`: session lifetime in seconds, `60` to `3600` (default: `600`)

Example one-way request:

```json
{
  "origin": "DVO",
  "destination": "MNL",
  "depart_date": "2026-07-02"
}
```

Example round-trip request:

```json
{
  "origin": "DVO",
  "destination": "MNL",
  "depart_date": "2026-07-02",
  "return_date": "2026-07-08"
}
```

Sample output:

```json
{
  "session_id": "a1b2c3d4e5f6",
  "origin": "DVO",
  "destination": "MNL",
  "depart_date": "2026-07-02",
  "return_date": null,
  "offer_count": 27,
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
      "airlines": ["Cebu Pacific"],
      "flight_numbers": ["964"]
    }
  ],
  "expires_at": "2026-05-21T14:10:00+00:00"
}
```

### `GET /api/v1/sessions`

Lists all active sessions.

Example request:

```http
GET /api/v1/sessions
```

Sample output:

```json
{
  "sessions": [
    {
      "session_id": "a1b2c3d4e5f6",
      "origin": "DVO",
      "destination": "MNL",
      "depart_date": "2026-07-02",
      "return_date": null,
      "offer_count": 27,
      "created_at": "2026-05-21T13:00:00+00:00",
      "expires_at": "2026-05-21T14:10:00+00:00",
      "is_expired": false
    }
  ],
  "count": 1
}
```

### `GET /api/v1/sessions/{session_id}`

Gets details of a specific session.

Example request:

```http
GET /api/v1/sessions/a1b2c3d4e5f6
```

Returns the same structure as the session creation response.

### `POST /api/v1/sessions/{session_id}/details`

Fetches details for a specific offer within an active session.

Request body arguments:

- `offer_index`: zero-based offer index from the session's offers list
- `return_offer_index`: optional zero-based return-offer index (for round-trip booking options)

Example one-way details request:

```json
{
  "offer_index": 0
}
```

Example round-trip return choices request:

```json
{
  "offer_index": 0
}
```

Example round-trip booking options request:

```json
{
  "offer_index": 0,
  "return_offer_index": 0
}
```

Key response fields:

- `selected_outbound_offer`: the chosen outbound offer
- `return_offers`: populated when a round-trip outbound offer is expanded
- `selected_itinerary`: populated when a final itinerary is known
- `booking_options`: populated when Google emitted `GetBookingResults`
- `return_offer_count`: convenience count for `return_offers`
- `booking_option_count`: convenience count for `booking_options`
- `timings`: includes `session_age_seconds` showing how long the session has been active

### `DELETE /api/v1/sessions/{session_id}`

Deletes a session and cleans up resources.

Example request:

```http
DELETE /api/v1/sessions/a1b2c3d4e5f6
```

Sample output:

```json
{
  "session_id": "a1b2c3d4e5f6",
  "status": "deleted"
}
```

## Legacy Scrape Endpoints

These endpoints still work but are not recommended for interactive applications. Each call triggers a full browser search.

### `POST /api/v1/scrape`

Runs a live scrape and returns the persisted summary run payload.

Request body arguments:

- `mode`: `auto`, `browser`, or `replay`
- `origin`: airport or city code
- `destination`: airport or city code
- `depart_date`: `YYYY-MM-DD`
- `return_date`: `YYYY-MM-DD` or omitted
- `passengers`: integer from `1` to `9`
- `cabin`: `economy`, `premium_economy`, `business`, or `first`
- `max_stops`: `0`, `1`, `2`, or omitted
- `retries`: integer from `1` to `5`
- `detail_level`: `summary` or `complete`
- `archive_root`: path string (default: `artifacts`)
- `headless`: boolean (default: `true`)

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

### `POST /api/v1/scrape/details`

Runs a second-stage scrape for one selected offer.

Use this endpoint after `POST /api/v1/scrape` when you need:

- booking options for one selected one-way offer
- return-flight choices for one selected round-trip outbound offer
- booking options for one selected round-trip combination

Additional request body arguments:

- `offer_index`: zero-based offer index from the summary response
- `return_offer_index`: optional zero-based return-offer index

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

## Report Endpoints

### `GET /api/v1/reports/recent-runs`

Returns recently persisted runs from SQLite.

Query arguments:

- `limit`: integer from `1` to `100`
- `archive_root`: path string, default `artifacts`
- `db_path`: optional explicit SQLite path

Example request:

```http
GET /api/v1/reports/recent-runs?limit=3
```

### `GET /api/v1/reports/cheapest-offers`

Returns the cheapest persisted offers, optionally filtered by route and date.

Query arguments:

- `limit`: integer from `1` to `100`
- `origin`: optional airport code
- `destination`: optional airport code
- `depart_date`: optional `YYYY-MM-DD`
- `archive_root`: path string, default `artifacts`
- `db_path`: optional explicit SQLite path

Example request:

```http
GET /api/v1/reports/cheapest-offers?origin=DVO&destination=MNL&depart_date=2026-07-02&limit=3
```

### `GET /api/v1/reports/mode-summary`

Returns aggregate statistics grouped by `executed_mode`.

Query arguments:

- `archive_root`: path string, default `artifacts`
- `db_path`: optional explicit SQLite path

Example request:

```http
GET /api/v1/reports/mode-summary
```

## Verified Endpoint Test Runs

These endpoints were tested live on `2026-05-21`:

- `GET /`
- `GET /health`
- `POST /api/v1/sessions`
- `GET /api/v1/sessions`
- `POST /api/v1/sessions/{id}/details`
- `DELETE /api/v1/sessions/{id}`
- `POST /api/v1/scrape`
- `POST /api/v1/scrape/details`
- `GET /api/v1/reports/recent-runs`
- `GET /api/v1/reports/cheapest-offers`
- `GET /api/v1/reports/mode-summary`

Important note:

- The application is configured to run on `0.0.0.0:8000`.
- During verification, port `8000` on this machine was already occupied by another unrelated Python service, so the live endpoint checks were executed against the same API on port `8001`.
