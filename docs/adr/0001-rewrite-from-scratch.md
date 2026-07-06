# ADR 0001: Rewrite from scratch instead of refactoring

- Status: accepted
- Date: 2026-07-06

## Context

The v1 codebase (~400 LOC, Python 3.12.4, Poetry, python-telegram-bot 21.4) worked but accumulated fragile choices: a 5-second polling loop to decide whether a notification is "due" (±30s window), naive datetimes stored as strings with timezones forced by hand, `Config()` instantiated globally in three modules, `locale.setlocale(it_IT)` depending on the host system, synchronous `requests` inside an async app, leftover debug statements, and no tests, Docker, or CI. The bot is currently not deployed anywhere (the old VPS no longer exists), so there is no migration or continuity constraint.

## Decision

Rewrite the entire bot from scratch (v2) with a 2026 stack, keeping the end-user functionality (channel reminders before each Serie A matchday lineup deadline, informational commands) but redesigning every internal that was wrong.

## Alternatives considered

- **Incremental refactor**: preserves git blame and lowers risk, but nearly every module needed rework; the refactor path would cost more than a clean rewrite at this size.

## Consequences

- No migration path for the old SQLite file: the database is regenerated from the calendar feed on first start.
- All v1 modules under `fantaformazionibot/` are deleted and replaced by `src/fantaformazionibot/`.
- User-visible texts are rewritten (improved copy, same language and tone).
