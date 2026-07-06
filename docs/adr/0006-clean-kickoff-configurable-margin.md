# ADR 0006: Store clean kickoff, derive deadline with a configurable margin

- Status: accepted
- Date: 2026-07-06

## Context

v1 stored "first match of the round − 5 minutes" as the matchday datetime: a derived value baked into the data, with the safety margin invisible and unchangeable. On Fantacalcio.it, lineups actually lock at the kickoff of the round's first match; the −5 minutes was a hidden safety cushion. Presentation code then added the 5 minutes back to display the real kickoff time.

## Decision

- Persist the **real kickoff** of each matchday (`MIN(kickoff)` across the round's fixtures), timezone-aware UTC.
- Derive the lineup deadline at computation time: `deadline = kickoff − DEADLINE_MARGIN`, where `DEADLINE_MARGIN` is an env setting (default `5m`, admin-configurable).

## Alternatives considered

- **Deadline = kickoff, no margin**: matches the literal Fantacalcio.it rule but leaves users with zero buffer; rejected in favor of an explicit, configurable margin.
- **Keep the baked-in −5 minutes**: perpetuates the dirty data model.

## Consequences

- Data in `matchdays` is a pure fact from the feed; policy (margin, offsets) lives in config.
- Changing the margin requires no data rebuild.
- All datetimes are tz-aware end to end: feed parsed as UTC, stored as ISO 8601 UTC, converted to `Europe/Rome` only for display (stdlib `zoneinfo`; no dateutil/pytz, no `locale.setlocale`).
