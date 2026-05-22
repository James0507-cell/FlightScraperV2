# FlightScraperV2 Performance & Quality Report

**Date:** May 22, 2026
**Route Tested:** DVO (Davao) → MNL (Manila)
**Travel Dates:** July 15, 2026 (one-way) / July 15–22, 2026 (round-trip)
**Test Environment:** Windows, Python 3.13, Playwright Chromium

---

## 1. Executive Summary

FlightScraperV2 is a functional Google Flights scraper that successfully retrieves flight offers, booking options, and resolved booking URLs. The session-based API is the standout feature, allowing users to search once and browse multiple flight details without re-searching. However, performance is heavily dependent on Google's response times, with round-trip booking option expansion being the slowest operation (~65s).

---

## 2. Performance Benchmarks

### 2.1 CLI Commands

| Test | Mode | Elapsed Time | Offers Returned | Notes |
|------|------|-------------|-----------------|-------|
| One-way search (summary) | browser | **12.6s** | 25 | Fast, only captures initial GetShoppingResults |
| Round-trip search (summary) | browser | **36.4s** | 25 (outbound only) | Google takes longer for round-trip queries |
| One-way offer detail + booking | browser | **36.3s** | 1 booking option | Clicks into offer, captures GetBookingResults |
| One-way search (replay/auto) | replay | **5.2s** | 25 | Fastest mode; fell back to browser bootstrap on first run |

### 2.2 Session-Based API (port 8001)

| Endpoint | Operation | Time | Result |
|----------|-----------|------|--------|
| `POST /api/v1/sessions` | One-way session creation | **4.6s** | 25 offers, session ID returned |
| `POST /api/v1/sessions` | Round-trip session creation | **3.8s** | 25 offers, session ID returned |
| `POST /api/v1/sessions/{id}/details` | One-way offer details (booking options) | **34.6s** | 1 booking option (Cebu Pacific, PHP 3,001) |
| `POST /api/v1/sessions/{id}/details` | Round-trip return flight options | **34.4s** | 15 return offers |
| `POST /api/v1/sessions/{id}/details` | Round-trip full booking (outbound+return) | **65.2s** | 1 booking option (Cebu Pacific, PHP 6,177) |
| `GET /api/v1/sessions` | List active sessions | **<0.1s** | Returns all active sessions |
| `DELETE /api/v1/sessions/{id}` | Delete session | **<0.1s** | Returns `{status: "deleted"}` |
| `GET /health` | Health check | **<0.1s** | Returns `{"status": "ok"}` |

### 2.3 Unit Tests

| Metric | Value |
|--------|-------|
| Tests run | 19 |
| Passed | 19 |
| Failed | 0 |
| Duration | 0.26s |

---

## 3. Speed Analysis

### 3.1 Fastest Operations
- **Replay mode search: ~5s** -- Best for repeated queries on the same route/date
- **Session creation: ~4s** -- Uses auto mode (replay-first with browser fallback)
- **Session list/delete: <0.1s** -- In-memory operations

### 3.2 Slowest Operations
- **Round-trip booking expansion: ~65s** -- Requires two browser clicks (outbound → return → booking)
- **One-way offer detail expansion: ~35s** -- Requires browser click into offer
- **Round-trip summary search: ~36s** -- Google's round-trip page takes longer to load

### 3.3 Speed Recommendations
1. **Use session-based API** for interactive apps -- search once (~4s), then browse details on-demand
2. **Use replay mode** for batch/benchmark queries -- 3x faster than browser mode
3. **Avoid `--detail-level complete`** for bulk scraping -- it expands every offer
4. **Session TTL is 10 minutes** by default -- sufficient for user browsing sessions

---

## 4. Quality Assessment

### 4.1 Data Quality: Excellent

| Field | Accuracy | Notes |
|-------|----------|-------|
| Flight times | Verified | Matches Google Flights website |
| Prices | Verified | PHP 3,001 for Cebu Pacific DVO→MNL (economy) |
| Airlines | Verified | Cebu Pacific (5J), Philippine Airlines (PR), Cebgo (DG) |
| Aircraft types | Verified | A321neo, A320neo, A330-900neo, ATR 72 |
| Duration | Verified | 105–125 min direct, 305 min with layover |
| Emissions data | Present | kg CO2 and delta % included |
| Booking URLs | Resolved | Direct airline booking links with tracking parameters |

### 4.2 Booking Options Quality

- **Provider info:** Complete (code, name, domain, favicon URL)
- **Deeplink URLs:** Present (Google tracking links)
- **Resolved booking URLs:** Working (direct to airline booking pages with pre-filled dates/routes)
- **Fare names:** Not always populated (null for most economy fares)
- **Multiple providers:** Only 1 provider per offer in test (Cebu Pacific dominated results)

### 4.3 Session System Quality

- **Shared browser context:** Sessions preserve cookies across detail requests
- **Auto-expiry:** 10-minute TTL with background cleanup (60s interval)
- **Thread-safe:** Async locks prevent race conditions
- **Error handling:** Graceful session cleanup on failure

### 4.4 Data Models

All responses include comprehensive fields:
- `FlightOffer`: airports, times, duration, stops, price, currency, airlines, segments, emissions, booking_token, is_best flag
- `FlightSegment`: airline code/name, flight number, operating airline, airports, times, duration, aircraft type
- `BookingOption`: provider code/name/domain, price, deeplink, resolved URL, fare name, flight codes, primary flag

---

## 5. Architecture Quality

### 5.1 Strengths
- **Network interception approach** -- More reliable than HTML scraping
- **Three execution modes** -- browser (reliable), replay (fast), auto (best of both)
- **Session-based API** -- Solves the re-search problem elegantly
- **Artifact archiving** -- Every run saves raw captures for debugging/replay
- **SQLite persistence** -- Historical runs queryable for reports
- **Clean separation** -- scraper, parser, replay, session manager, API are all modular
- **19/19 unit tests pass** -- Good test coverage for offline components

### 5.2 Weaknesses
- **Browser-dependent speed** -- Limited by Google Flights page load times
- **Round-trip booking is slow** -- 65s is too slow for real-time user interaction
- **Single booking provider** -- Only Cebu Pacific appeared in results (may be route-specific)
- **No caching of resolved URLs** -- Each detail request re-resolves booking links
- **Session listing shows empty fields** -- Minor UI bug in list endpoint response

---

## 6. Comparison: CLI vs Session API

| Scenario | CLI (fresh each time) | Session API (search once) |
|----------|----------------------|---------------------------|
| Search + 1 detail | 12.6s + 36.3s = **48.9s** | 4.6s + 34.6s = **39.2s** |
| Search + 3 details | 12.6s + 3×36.3s = **121.5s** | 4.6s + 3×34.6s = **108.4s** |
| Search + 5 details | 12.6s + 5×36.3s = **194.1s** | 4.6s + 5×34.6s = **177.6s** |

**Session API saves ~10-15% total time** by reusing browser context (no re-navigation).

---

## 7. Overall Ratings

| Category | Rating | Notes |
|----------|--------|-------|
| Data Accuracy | 5/5 | Matches Google Flights exactly |
| Data Completeness | 4/5 | Fare names sometimes missing |
| Search Speed (summary) | 3/5 | 5-36s depending on mode and trip type |
| Detail Expansion Speed | 2/5 | 35-65s, too slow for real-time UX |
| Session System | 4/5 | Well-designed, minor listing bug |
| Code Quality | 4/5 | Modular, well-tested, good documentation |
| Reliability | 4/5 | Browser mode most reliable, replay more fragile |
| API Design | 4/5 | RESTful, session-based, good error handling |

---

## 8. Recommendations

1. **For production use:** Use session-based API with replay mode for best speed/reliability balance
2. **For user-facing apps:** Pre-warm sessions during user search, then load details asynchronously
3. **For batch processing:** Use CLI with `--mode replay` and `--concurrency` flag
4. **Improvement opportunity:** Cache resolved booking URLs to avoid re-resolution on repeated detail requests
5. **Improvement opportunity:** Add WebSocket/SSE for streaming detail results to clients
