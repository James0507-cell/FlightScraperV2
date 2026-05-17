# Validation And Benchmark

## Scope

This document records the live validation and benchmark results collected on `2026-05-17` for the current Google Flights scraper implementation.

The comparison covered:

- `browser` mode
  - Full Playwright UI submission.
- `replay` mode
  - One browser bootstrap query to capture session state and request template.
  - Follow-up request replay through the same Playwright browser context.

## Validated Runs

### Route: `DVO -> MNL`, round trip, `2026-07-02` to `2026-07-08`, `max_stops=0`

Browser mode:

- Command:
  - `python main.py --mode browser --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 2`
- Result:
  - Success
  - `offer_count = 25`
  - Artifact: `artifacts/20260517T121315Z`
- Observed wall time:
  - About `11.4s`

Replay mode:

- Command:
  - `python main.py --mode replay --origin DVO --destination MNL --depart-date 2026-07-02 --return-date 2026-07-08 --max-stops 0 --retries 2`
- Result:
  - Success
  - `offer_count = 25`
  - Artifact: `artifacts/20260517T121402Z`
- Observed wall time:
  - About `56.2s`

### Data-quality comparison for the successful `DVO -> MNL` runs

Compared artifacts:

- Browser: `artifacts/20260517T121315Z/offers.json`
- Replay: `artifacts/20260517T121402Z/offers.json`

Observed:

- Offer counts matched: `25` vs `25`
- Normalized fields matched for all compared offers:
  - `origin_airport`
  - `destination_airport`
  - `departure_time`
  - `arrival_time`
  - `price`
  - `flight_numbers`
  - `airlines`
- Booking tokens differed, which is expected for separate live sessions.

Conclusion:

- Replay mode can return the same normalized offer data as browser mode on the validated route.

## Batch Benchmark

Query file used:

- [benchmark-queries.json](C:/Users/Admin/PycharmProjects/FlightScraperV2/benchmark-queries.json)

Contained routes:

1. `DVO -> MNL`
2. `CEB -> MNL`
3. `MNL -> DVO`

### Browser mode batch

- Command:
  - `python main.py --mode browser --query-file benchmark-queries.json --concurrency 1 --retries 2`
- Result:
  - Success
  - Query 1: `25` offers
  - Query 2: `30` offers
  - Query 3: `24` offers
- Artifacts:
  - `artifacts/20260517T121529Z`
  - `artifacts/20260517T121624Z`
  - `artifacts/20260517T121717Z`
- Observed wall time:
  - About `168.5s`

### Replay mode batch

- Command:
  - `python main.py --mode replay --query-file benchmark-queries.json --concurrency 1 --retries 2`
- Result:
  - Success
  - Query 1:
    - Executed as `browser_bootstrap`
    - `25` offers
    - Total time: about `4.91s`
  - Query 2:
    - Executed as `replay`
    - `30` offers
    - Total time: about `0.60s`
  - Query 3:
    - Executed as `replay`
    - `24` offers
    - Total time: about `0.22s`
- Observed wall time:
  - About `40.7s`

Important detail:

- The successful batch used the new resilient replay flow:
  - First query establishes a browser bootstrap and replay template.
  - Later queries run as replay requests through the same session context.
  - Batch results now report per-query `requested_mode`, `executed_mode`, `timings`, and `notes`.

## Additional Validation Attempt

### Earlier instability note

Before the resilient replay batch flow was added, some validation attempts on secondary routes failed due browser bootstrap and submission instability.

That behavior is still relevant:

- The browser path is still intermittently flaky on some live runs.
- The replay path now tolerates that better because bootstrap and replay are measured separately and batch execution is resilient to per-query failures.

## Interpretation

### What is validated

- Browser mode can succeed and produce stable normalized results.
- Replay mode can successfully reproduce browser-mode results for at least one live route.
- Replay output quality, on the successful route, matched browser output quality after normalization.

### What is not yet validated

- Replay mode is not yet stable enough for multi-route batch use.
- The replay batch failure currently happens during browser bootstrap, not during the replay request itself.
- The current timing does not yet prove replay is faster overall because the current replay flow still pays a full browser bootstrap cost.

## Benchmark Conclusion

Current measured behavior:

- Browser single-query success:
  - `~11.4s`
- Replay single-query success:
  - `~56.2s`
- Browser three-query batch success:
  - `~168.5s`
- Replay three-query batch success:
  - `~40.7s`
  - Bootstrap query: `~4.91s`
  - Replay query 2: `~0.60s`
  - Replay query 3: `~0.22s`

Important caveat:

- Single-query replay is still slower than plain browser mode because it includes browser bootstrap overhead.
- Replay becomes a speed win when one bootstrap supports many subsequent replayed queries.
- The new batch benchmark demonstrates that this advantage is now real in the current implementation.

## Next Engineering Step

The next step should be to harden bootstrap and isolate replay performance from bootstrap cost.

Recommended work:

1. Separate bootstrap timing from replay timing in code and logs.
2. Add a benchmark command that records:
   - bootstrap duration
   - replay request duration
   - parse duration
   - total duration
3. Reuse a single successful bootstrap across many replayed queries.
4. Add fallback behavior:
   - If replay fails, fall back to browser submission for that query.
5. Investigate why some routes intermittently fail before `GetShoppingResults` is returned.

## Summary

Status after validation:

- Replay correctness: validated on successful routes
- Replay stability: improved and usable for batch runs with current fallback/reporting
- Replay speed advantage: demonstrated for multi-query batches after bootstrap
- Browser baseline: validated and working
