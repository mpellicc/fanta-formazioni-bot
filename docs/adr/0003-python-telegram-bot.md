# ADR 0003: python-telegram-bot ~22.8

- Status: accepted
- Date: 2026-07-06

## Context

The bot needs a Telegram Bot API framework with command handling, error handling, and time-based job scheduling. v1 used python-telegram-bot 21.4.

## Decision

Stay on **python-telegram-bot**, upgraded to `~=22.8` (latest as of June 2026, actively maintained, full Bot API 10 support), with the `job-queue` extra for its APScheduler-backed `JobQueue`. Updates are received via **long polling** (no public HTTPS endpoint needed on the target VM).

## Alternatives considered

- **aiogram 3.x**: excellent modern framework, stronger for high-concurrency bots, but has no built-in scheduler (would require wiring APScheduler manually) and offers no benefit at this bot's traffic level.
- **Raw Bot API calls (httpx)**: minimal dependencies but reimplements dispatching, error handling, and scheduling for no gain.
- **Webhooks instead of polling**: requires exposing a TLS endpoint; unnecessary complexity for a single low-traffic bot on a VM.

## Consequences

- `JobQueue` (`run_once`, `run_daily`) is the single scheduling mechanism (see ADR 0005).
- PTB already depends on httpx, which is reused for calendar downloads (no `requests`).
