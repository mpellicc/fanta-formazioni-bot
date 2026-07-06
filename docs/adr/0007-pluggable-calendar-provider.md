# ADR 0007: Pluggable calendar provider (fixturedownload CSV first)

- Status: accepted
- Date: 2026-07-06

## Context

v1 hardcoded fixturedownload.com's CSV export as the only source of the Serie A calendar. The service is free and keyless but its long-term reliability is unknown; a structured football API may replace it later. Which source is used is an admin decision, not a user-facing option.

## Decision

Define a `CalendarProvider` protocol (`calendar/base.py`) with a single async method returning the season's matchdays (`round`, `kickoff` UTC). Implementations are selected via the `CALENDAR_PROVIDER` env setting through a small factory. The only implementation today is `fixturedownload`: it downloads the UTC CSV variant with httpx and parses it in memory (nothing written to disk).

CSV parsing is a pure function separated from the HTTP download so it can be unit-tested against a fixture file.

## Alternatives considered

- **Switch to a football API now** (e.g. football-data.org): richer data but needs an API key and rate-limit handling; deferred until fixturedownload proves unreliable.
- **Hardcode CSV again**: cheapest, but makes the eventual swap a refactor instead of a new class + env change.

## Consequences

- Adding an API provider = one new module implementing the protocol + a factory entry.
- The CSV feed URL stays configurable (`CALENDAR_URL`) with a `{season_year}` placeholder; season year rolls over on July 1st.
