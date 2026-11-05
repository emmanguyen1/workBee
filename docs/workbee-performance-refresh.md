# Faster search, on-demand refresh, and usable saved listings

## Why the page showed zero

The previous website required every source observation to be within thirty
minutes. When background collection was stopped to save battery, listings aged out
without being confirmed closed. This made “nothing was checked recently” look like
“there are no opportunities.”

The website now includes **last-known-open listings observed within seven days**.
Checks older than thirty minutes are clearly labelled as needing a recheck. Source
failures preserve prior snapshots with unknown availability; they do not imply
closure. Confirmed source removals and explicit expired deadlines remain excluded.
A negative verification stays excluded until a newer successful source observation
supersedes it. Simplify rows still require explicit opt-in and retain their separate
community/unverified labels.

The API keeps its strict compatibility mode: `current_only:true` without
`include_stale:true` still requires recent source evidence. The website opts into
`include_stale:true`; it never presents cached rows as freshly verified. Bee uses
this same seven-day range and labels cached source links as needing rechecking.

## Search cache and isolation

A bounded in-process cache holds at most two prepared **public** catalogs.
Deduplication, country/state parsing, career classification, industry tags,
class-year wording and deadline extraction run once per loaded snapshot. Empty
keyword queries no longer build/lowercase every full description. A profile's
canonical evidence map is built once per request, rather than once per job.

Profiles, evidence, personal match results, preferences, notes and sessions never
enter the shared catalog cache. Each search recalculates availability/freshness,
deadline expiry, matching and filters. Source writes/failures/verifications
invalidate the local cache immediately. Concurrent misses share one load.

After sixty seconds a request checks a small public source/verification revision.
An unchanged snapshot can be reused rather than reloading large descriptions.
Prepared entries have a five-minute hard maximum age and a two-entry memory bound.
Reads use a repeatable-read transaction so rows and source metadata describe the
same database snapshot. The cache does no idle polling or scheduled prewarming.

Source snapshots now use batched database writes within the existing atomic
transaction, and a partial index supports open-listing freshness queries.
Description normalization runs off the request event loop, with cooperative
cancellation during manual refreshes.

The `Server-Timing` response header reports catalog and search durations; private
responses remain `Cache-Control: no-store`. Large first loads remain slower than
cached requests. Lazy description loading would be the next useful improvement.

## Local benchmark

The pre-change read-only profile used 14,017 stored open rows (13,908 results after
deduplication). Loading took 14.2 seconds, and profiled search processing took 12.0
seconds, including repeated location parsing and URL deduplication.

A same-catalog HTTP benchmark after prepared caching measured:

| Request | Seconds |
| --- | ---: |
| First uncached full-catalog request | 31.14 |
| Repeated search | 0.50 |
| United States filter | 1.04 |
| Python keyword filter | 2.08 |
| Two-skill profile ranking | 6.60 |

These are local measurements, not latency guarantees. The cold run overlapped
regression checks, and profile size, catalog changes, source count and machine
load affect timings. The website’s seven-day cached-listing mode then returned 11,539 results in
13.44 seconds cold and 0.36 seconds on repeat. A real APHA-only manual refresh
completed successfully and returned 13 freshly checked listings with zero recheck
flags. The zero-results correction is separately tested against aged snapshots,
known removals and expired deadlines.

## Explicit refresh controls

The discovery page supports all eligible sources, selected employers, or one
source. Simplify is included in a full refresh only when its discovery option is
on. It shows per-source last successful checks and failed-attempt timestamps,
progress, errors, and a cancel control. Results reload when the finite job ends.
Only an active refresh is polled; polling pauses when the tab is hidden and stops
on completion or failure. Loading a page never starts a feed import.

`POST /api/careers/refresh` accepts allowlisted employer names or source keys, not
URLs. Requests must come from the same origin. A PostgreSQL advisory lock prevents
concurrent manual imports; another request joins the current job rather than
starting a duplicate. Sources successfully checked within five minutes are skipped;
failed checks have a one-minute retry cooldown.

Progress is persisted in `career_refreshes`, so page reloads can recover it. Stale
jobs whose process/lease disappeared are reported as interrupted. Cancelling keeps
already completed snapshots and rolls back an incomplete source write. The server
cancels active work on shutdown. Completed job records older than seven days are
pruned when starting another manual refresh.

A failed or malformed feed is never saved as an empty snapshot. Previously stored
rows are preserved and the error is visible. Source availability continues to be
evidence of listing presence, not a guarantee that an application form accepts
submissions.

Only workBee and Postgres are needed. The collector, Redis and Redis bridge remain
stopped unless explicitly enabled. Manual refresh requires no new service, API key
or periodic worker.
