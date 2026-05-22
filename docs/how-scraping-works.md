# How The Scraper Works

This document explains how the Google Flights scraper works end to end.

## High-Level Design

The scraper is built around a network-first approach.

It does not primarily scrape visible result cards from the page. Instead, it captures the backend flight results request that Google Flights sends and parses the returned response.

There are two execution paths:

- `browser` mode
- `replay` mode

Both paths are trying to obtain the same live Google Flights response:

- `GetShoppingResults`

## Main Goal

For each flight query, the scraper wants to produce normalized offer data such as:

- origin
- destination
- departure time
- arrival time
- duration
- stops
- airlines
- flight numbers
- price
- emissions

The scraper stores both:

- the raw captured network data
- the normalized parsed offers

## Main Files

The main modules are:

- [main.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/main.py)
- [cli.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/cli.py)
- [google_flights.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/google_flights.py)
- [session_manager.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/session_manager.py)
- [replay_client.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/replay_client.py)
- [replay.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/replay.py)
- [parser.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/parser.py)
- [models.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/models.py)
- [storage.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/storage.py)
- [database.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/database.py)
- [api.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/api.py)

## Flow Overview

The runtime flow is:

1. The CLI receives a flight query.
2. A scraper path is selected:
   - `browser`
   - `replay`
   - `auto`
3. A live Google Flights request is executed.
4. The `GetShoppingResults` response is captured.
5. The raw response is parsed into normalized offers.
6. Optional detail expansion can fetch one offer's return choices or booking options.
7. The run is archived under `artifacts/`.
8. Summary runs are persisted into SQLite.

## 1. Entry Point

The CLI starts in [main.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/main.py), which delegates to [cli.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/cli.py).

The CLI supports:

- single-query runs
- batch runs from a JSON file
- benchmark runs
- replay-template printing
- SQLite-backed reports

Important mode behavior:

- `--mode browser`
  - always use the Playwright UI path
- `--mode replay`
  - bootstrap if needed, then try direct request replay
- `--mode auto`
  - currently treated as replay-first behavior

## 2. Browser Mode

Browser mode is implemented in [google_flights.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/google_flights.py).

This mode uses Playwright to behave like a user:

1. Launch the browser.
2. Open Google Flights.
3. Fill:
   - origin
   - destination
   - dates
   - passengers
   - cabin
   - stop filters
4. Trigger the search.
5. Wait for the live backend request and response.
6. Capture the returned payload.

This path is slower but safer because it follows the UI directly.

### Summary Vs Detail Expansion

Browser mode now has two layers:

- `summary`
  - default
  - stops after the initial `GetShoppingResults`
  - returns outbound offers only
- offer-details flow
  - reruns the query for one selected offer
  - can fetch:
    - booking options for one-way offers
    - return-flight choices for one selected round-trip outbound offer
    - booking options for one selected round-trip combination

This split exists because the old all-in-one browser flow replayed booking lookups for every parsed offer, which made one scrape behave like many follow-up scrapes.

### Why Browser Mode Exists

Browser mode is useful because:

- it works even if replay is not ready yet
- it is closer to how a real user interacts with the site
- it provides a bootstrap path for replay mode
- it is the fallback when replay fails

## 3. Replay Mode

Replay mode is implemented across:

- [replay.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/replay.py)
- [replay_client.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/replay_client.py)

Replay exists to make repeated scraping faster.

Instead of using the full page UI for every query, replay mode reuses the backend request shape that Google Flights already uses internally.

### Replay Concept

Replay mode works like this:

1. Run one real browser query.
2. Capture the request Google sent to `GetShoppingResults`.
3. Extract the internal request body template.
4. Replace route/date/query fields with a new `FlightQuery`.
5. Send that rebuilt request directly through the current browser session context.
6. Parse the returned response.

This is still live scraping. It is not cached or fake data.

The difference is only:

- browser mode sends the request by interacting with the page
- replay mode sends the request directly after learning its structure

### Why Replay Is Faster

Replay avoids repeated UI work such as:

- opening and settling page state
- clicking and typing through the full form
- waiting for page interactions on every query

One browser bootstrap can support many replayed queries.

That is why replay is the main speed path for batches.

### Why Replay Can Be More Fragile

Replay depends on Google’s internal request format staying usable.

It can break if:

- request parameters change
- session requirements change
- cookies or tokens are no longer valid
- Google changes the payload structure

That is why replay mode includes fallback behavior.

## 4. What `f.req` Means

Google Flights does not expose a simple public API in this flow.

The request body for `GetShoppingResults` contains an internal field called `f.req`.

That field carries structured request data such as:

- route
- dates
- trip type
- passenger count
- cabin
- stop filters

The scraper uses a real captured request as a template, then rebuilds the `f.req` body for new queries.

That logic is handled in [replay.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/replay.py).

## 5. Parsing The Response

The response parser is in [parser.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/parser.py).

Google’s returned data is not a clean, documented API schema. The parser has to normalize a nested internal payload.

The parser does things such as:

- remove the XSSI prefix
- inspect nested arrays and embedded JSON strings
- extract flight offers
- extract segment details
- normalize them into stable Python data models

Parsed offers include fields like:

- `origin_airport`
- `destination_airport`
- `departure_time`
- `arrival_time`
- `duration_minutes`
- `stops`
- `price`
- `currency`
- `airlines`
- `flight_numbers`
- `booking_token`

The same parser is also reused for detail expansion:

- the initial round-trip summary returns outbound offers
- selecting one outbound offer yields a second `GetShoppingResults` payload containing return offers
- selecting a final itinerary yields `GetBookingResults`

## 6. Data Models

The normalized structures are defined in [models.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/models.py).

Important models include:

- `FlightQuery`
- `FlightSegment`
- `FlightOffer`
- `NetworkCapture`
- `ScrapeRun`
- `OfferDetails`

These models keep the rest of the system independent from Google’s raw internal payload shape.

## 7. Archiving Raw And Parsed Data

Archiving is handled by [storage.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/storage.py).

Each successful run creates an artifact directory under `artifacts/`.

Typical files include:

- `capture.json`
- `request.txt`
- `response.txt`
- `offers.json`
- `run.json`

Offer-detail runs additionally write:

- `details.json`

These are useful for:

- debugging parser changes
- replay-template generation
- validating live behavior
- keeping historical scrape evidence

## 8. SQLite Persistence

SQLite persistence is handled by [database.py](C:/Users/Admin/PycharmProjects/FlightScraperV2/flightscraperv2/database.py).

Archived runs are automatically written into:

- `artifacts/scraper.sqlite`

The database currently stores:

- `runs`
- `offers`
- `segments`

This makes it possible to inspect historical scrape results without reopening the raw artifact files.

The CLI can already report:

- recent runs
- cheapest offers
- mode summaries

## 9. Fallback Behavior

Replay mode is not trusted blindly.

If replay fails, the system can fall back to the browser path for that query.

This is important because:

- browser mode is slower but safer
- replay mode is faster but more brittle

The execution mode recorded for a run may therefore be:

- `browser`
- `browser_bootstrap`
- `replay`
- `browser_fallback`

## 10. Batch Scraping

The CLI supports batch execution from a query file.

In replay-oriented batch runs, the expected pattern is:

1. First query runs through browser bootstrap.
2. Later queries try direct replay.
3. Failed replay queries can fall back to browser mode.

This design is what gives the scraper its high-speed path.

## 11. Why Playwright Is Still Needed

Even with replay mode, Playwright still matters.

It is needed for:

- initial browser bootstrap
- session creation
- live request discovery
- fallback scraping
- resilience when replay stops working

So Playwright is not replaced by replay. Replay is built on top of a Playwright-based session bootstrap.

## 12. Why Beautiful Soup Is Not The Main Tool

Beautiful Soup is not the main extraction layer because Google Flights is not primarily a static HTML problem.

The main data comes from live JavaScript-driven backend requests.

Beautiful Soup would only be useful for secondary tasks such as:

- parsing saved HTML fragments
- post-processing static markup
- small offline HTML extraction tasks

The main scraper depends on:

- Playwright
- network interception
- direct request replay
- custom payload parsing

## 13. Simple Mental Model

The easiest way to think about the scraper is:

- browser mode:
  - use the website like a user
- replay mode:
  - copy the network call the website made, then send that call again with new values

Both paths still scrape live Google Flights data.

## 14. Current Strengths

The current design already gives the project:

- live Google Flights scraping
- network-first extraction
- replay-based speed gains
- raw artifact archiving
- SQLite persistence
- benchmark support
- report queries over stored runs
- session-based API for interactive trip planning applications

## 15. Session-Based API for Trip Planning Apps

Version 0.2.0 introduces a session-based API designed specifically for interactive trip planning applications.

### How It Works

Instead of re-running the full browser search every time a user clicks a flight card, the session-based approach:

1. Creates a session with an initial search (returns offers)
2. Keeps the browser context alive
3. Fetches details for any offer using the same session
4. Automatically cleans up expired sessions

### Why This Matters

For a trip planning app where users browse multiple flight cards:

- **Legacy approach**: Each detail click triggers a full ~35 second re-search
- **Session approach**: Initial search takes ~6 seconds, subsequent detail fetches share the browser context

### Session Lifecycle

```
POST /api/v1/sessions → Create session (runs initial search)
    ↓
GET  /api/v1/sessions → List active sessions
    ↓
POST /api/v1/sessions/{id}/details → Fetch offer details
    ↓
DELETE /api/v1/sessions/{id} → Clean up session
```

Sessions auto-expire after 10 minutes (configurable via `session_ttl`).

### Implementation

The session manager (`session_manager.py`) handles:

- Browser context sharing across detail requests
- Session creation and cleanup
- Automatic expiry with background cleanup task
- Thread-safe session access with async locks

See `docs/client-implementation-guide.md` for client-side implementation examples.

## 16. Current Limitations

The current implementation still has important limits:

- replay depends on internal Google request formats
- browser automation can still be flaky across live runs
- Google does not always emit detail responses (`GetBookingResults`) consistently for every session
- parsing is tied to the currently observed payload structure
- anti-blocking behavior is still basic
- broader route coverage still needs validation

## 17. Summary

The scraper is a Playwright-based, network-first Google Flights scraper with a replay acceleration layer and session-based API for interactive applications.

In practice:

- browser mode summary discovers and captures the initial live results
- detail expansion is a second scrape for one selected itinerary
- replay mode reuses the discovered request format for speed
- session-based API enables interactive trip planning with shared browser context
- parser logic converts Google's internal payload into stable offer data
- storage and SQLite keep both raw evidence and normalized results available for analysis
