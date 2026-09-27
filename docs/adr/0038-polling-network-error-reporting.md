# ADR 0038: Polling network errors become a digest and an outage alert

- Status: accepted
- Date: 2026-09-27

## Context

Both bots regularly post `telegram.error.NetworkError` tracebacks to the debug chat. The
current policy (`telegram/errors.py`) reports a polling `NetworkError` (no update, no job) at
most once every 10 minutes and every other error immediately.

Five days of container logs (both bots, since the last restart on 2026-09-22) show:

- **`httpx.ReadError`**: 1–3 per day, always in `get_updates`, isolated or a few within
  minutes. The next poll always succeeded.
- **`Bad Gateway`**: every night around 01:11 UTC, on both bots, a burst of 2–6 errors
  over ~10 seconds — Telegram answering 502. The 10-minute throttle already hides all but
  the first.
- **No network error in jobs**: no reminder was lost.

PTB's `network_retry_loop` retries polling errors forever (backoff up to 30s), so every one
of these healed on its own. The upstream guide
([Handling network errors](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Handling-network-errors))
treats this as normal for long polling and leaves the reporting policy to each application.

The throttled traceback is the wrong signal for both cases that matter: it is noise when
the error heals in seconds, and it says nothing when polling stays down, because the
throttle hides the continuation.

## Decision

Polling network errors (same predicate as today: `update is None`, `context.job is None`,
`NetworkError` but not `BadRequest`) are **no longer reported one by one**. They are logged
and tracked in memory. Every other error keeps being reported immediately, with traceback.

1. **Outage alert.** The first polling error opens a *streak* (`first_error_at`); each
   error updates `last_error_at` and the last error's class/message. A job repeating every
   60 seconds checks the streak:
   - streak open for **more than 5 minutes** and not yet alerted → one short message, no
     traceback: duration and last error.
   - no error for **more than 90 seconds** → the streak is closed; if it had been alerted,
     one "recovered after X min" message.

   PTB exposes no hook for a *successful* poll, so recovery is inferred from silence. 90s
   exceeds the worst gap between two failing polls (30s max backoff + the request's own
   timeouts), so an ongoing outage cannot look recovered.

2. **Daily digest** at **09:00 Europe/Rome**: one line with the count per error kind
   (e.g. `4× httpx.ReadError, 5× Bad Gateway`) over the last 24 hours, then the counters
   reset. Nothing is sent when the count is zero.

State is in memory only (module-level, like the current throttle timestamp): a restart or
deploy loses the counts since the last digest. That is acceptable for a noise digest. If the
process restarts in the middle of an outage, the new process opens a new streak on its first
error.

## Alternatives considered

- **Tune the network layer** (the guide's timeouts, polling `timeout`, TCP keepalive via
  `HTTPXRequest(socket_options=...)`). Rejected for now: the errors hit a `get_updates`
  connection that is never idle, and the nightly 502s come from Telegram. Nothing in the
  data points at a setting we could fix. Revisit if the digest shows a trend.
- **Keep the throttle, just shorten the message.** Still noise, still no signal for a
  sustained outage.
- **Persist the counters in `bot_events`** (ADR 0028/0029). Restarts would lose nothing, but
  it's a schema-level commitment for a noise metric. Rejected.
- **Detect recovery with an active probe** (`get_me` from the job). It adds traffic and a
  second failure path, and still says nothing about polling itself. Rejected.

## Consequences

- The debug chat stops getting tracebacks for self-healing polling blips; it gets one line
  a day, and a real alert only for outages longer than 5 minutes.
- Network errors in handlers and jobs (e.g. a reminder send) still reach the debug chat
  immediately, with traceback.
- An outage shorter than 5 minutes only shows up in the digest.
