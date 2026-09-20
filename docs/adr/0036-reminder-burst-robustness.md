# ADR 0036: Reminder bursts survive rate limits and dispatch lag

- Status: accepted
- Date: 2026-09-19

## Context

Every subscription's reminder for a given round and offset is planned at the same instant
(`deadline − offset`, ADR 0005/0006), so when that instant arrives the `JobQueue` fires one
`run_once` job per chat in a single burst. Two properties of that burst do not scale, and
neither is visible at today's few dozen subscriptions:

1. **No rate limiting.** `ApplicationBuilder` is built without a rate limiter, so the burst
   issues its `sendMessage` calls with no throttling. Past Telegram's ~30 messages/second
   ceiling the API answers `429` (`RetryAfter`). In `send_reminder_job` a `RetryAfter` is not
   a dead-chat error, so it falls through to the `raise` branch: the reminder is **not** marked
   sent, is **not** retried, and no later run reschedules it — it is simply lost.

2. **Silent drop of the burst's tail.** APScheduler runs the burst's jobs as cooperative
   asyncio tasks and checks misfire *inside* `run_coroutine_job`, when each task finally runs:
   if `now − run_time > misfire_grace_time` the job is marked `EVENT_JOB_MISSED` and skipped
   (`continue`), so its callback never runs. PTB does not set `misfire_grace_time`, so the
   APScheduler default of **1 second** applies. The tail tasks in a same-instant burst start
   late by roughly the sum of the preceding jobs' synchronous preludes (the sqlite checks
   before the first `await`); once that cumulative lag crosses 1s, the last reminders are
   dropped with only a warning. This is the "genuine lateness shows up as a *missing*
   reminder" failure the ADR 0005 amendment described — benign at grace-vs-scale of today,
   a correctness cliff as subscriptions grow.

The observed per-reminder "drift" in the logs (~1 ms, growing across the burst) is a symptom
of the same serialisation — the synchronous prelude of each job runs before it yields — but
the drift value itself is harmless. The two failure modes above are the ones that matter.

Note on what is *not* a problem: the reminder text is computed (`messages.reminder(...)`)
before `send_message` is called, so a rate limiter's wait — which happens inside
`send_message` — cannot change the residual time a reminder announces. The text depends only
on when the job's callback starts, not on when the HTTP call is dispatched.

## Decision

Two changes, both about surviving a large burst; the reminder-text logic is left untouched
because it is already correct (ADR 0005 amendment).

1. **Add `AIORateLimiter(max_retries=3)`** to the application builder, and the
   `rate-limiter` extra to the `python-telegram-bot` dependency. This throttles outgoing
   sends under Telegram's documented limits and, crucially, **retries `RetryAfter`** up to
   three times instead of letting a flood-control response destroy the reminder. The
   `max_retries` default is `0` (throttle but do not retry), so it is set explicitly.

2. **Raise `misfire_grace_time` to 30 seconds** for the reminder jobs, via
   `job_kwargs={"misfire_grace_time": 30}` on `run_once` in `reschedule_reminders`. A burst
   whose dispatch spreads over tens of seconds no longer drops its tail. The value is scoped
   to the reminder jobs, not the scheduler default, so the daily calendar-refresh job keeps
   the stricter default.

Together they produce a coherent honesty ladder for a late reminder, keyed on the existing
`SCHEDULING_TOLERANCE` (5s) that selects the text's reference instant:

- **0–5s late** — the reminder states the nominal offset ("5 minuti").
- **5–30s late** — the reminder is still sent, stating the real remaining time from the wall
  clock ("4 minuti"); a late reminder must tell the truth (ADR 0005 amendment).
- **>30s late** — the job is dropped: past that point the ping is stale, and a nominal text
  would be misleading anyway.

30s of grace absorbs a dispatch spread of tens of thousands of same-instant jobs (the spread
is the sum of ~1 ms synchronous preludes), which is far beyond any realistic subscriber
count, while still discarding a genuinely stale job.

## Alternatives considered

- **Batch / multicast sends.** Telegram has no multicast: every chat needs its own
  `sendMessage`. "Batching" could only reorder or group calls, not reduce their number, so it
  does not address either failure mode.
- **Rate limiter alone.** Throttling makes the burst well-behaved against Telegram but does
  nothing about the misfire cliff, which drops jobs before any send is attempted.
- **Raising `misfire_grace_time` alone.** Keeps the tail alive but leaves `RetryAfter`
  losses under load. Both changes are needed.
- **Moving the sqlite checks out of the per-job prelude** (to shrink the dispatch spread).
  A real optimisation, but premature: 30s of grace already covers scales we will not reach,
  and it would complicate the pure/DB boundary for no present benefit.

## Consequences

- Reminders survive Telegram flood control and same-instant bursts up to scales far past the
  current few dozen subscriptions; the two silent-loss paths are closed.
- New runtime dependency `aiolimiter` (via the `rate-limiter` extra); no new environment
  variable, no config surface.
- A known ceiling remains and is inherent to a single bot: at ~30 sends/second a burst of
  many thousands takes minutes to deliver in full. For long offsets (1h, 24h) this is
  invisible; for a short urgent offset a very large audience would receive the last pings
  close to the deadline. Addressing that (a broadcast path, multiple bot tokens) is out of
  scope until the audience is large enough to need it.
- The ADR 0005 amendment's reliance on the 1s default grace to guarantee "late = missing, not
  shifted" is superseded here: lateness up to 30s now yields a sent reminder with wall-clock
  text, which the amendment's own tolerance logic already handles correctly.
