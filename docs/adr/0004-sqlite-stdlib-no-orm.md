# ADR 0004: SQLite via stdlib, no ORM

- Status: accepted
- Date: 2026-07-06

## Context

The bot persists a handful of rows: ~38 matchdays per season, a few subscriptions, and sent-reminder markers. Query volume is a few reads/writes per day.

## Decision

Use the stdlib `sqlite3` module with WAL mode, wrapped in a thin repository module (`storage/repository.py`) that owns the schema and all SQL. Datetimes are stored as ISO 8601 UTC strings.

## Alternatives considered

- **SQLAlchemy / an ORM**: heavy for three tiny tables; hides the ~10 queries we have.
- **aiosqlite**: async wrapper, but each query is sub-millisecond and extremely infrequent; blocking the event loop for microseconds is acceptable and keeps the code simpler.
- **Managed DB (Postgres, D1, ...)**: operational overhead and cost for no benefit; SQLite on a Docker volume is fully sufficient.

## Consequences

- The repository module is the only place with SQL; swapping storage later means reimplementing one file.
- Schema is created idempotently at startup (`CREATE TABLE IF NOT EXISTS`); no migration framework. Schema changes are applied by hand or by regenerating the DB (all data is derivable from the feed except sent-reminder markers).
