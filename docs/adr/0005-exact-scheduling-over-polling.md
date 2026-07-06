# ADR 0005: Exact reminder scheduling instead of polling

- Status: accepted
- Date: 2026-07-06

## Context

v1 ran a job every 5 seconds that checked whether "now" fell inside a ±30-second window around each notification time. This burned CPU continuously, made timing accuracy depend on the window size, and duplicated dedup logic on every tick.

## Decision

Compute the exact datetime of every future reminder (deadline − offset, per subscription) and schedule each one as a `JobQueue.run_once` job. The reminder plan is recomputed and rescheduled:

1. at startup (after the initial calendar fetch), and
2. after every daily calendar refresh (kickoff times change during the season).

Rescheduling removes all previously scheduled reminder jobs (identified by a name prefix) and schedules the current plan. The `sent_reminders` table dedupes across restarts; reminders whose time already passed are never sent retroactively.

## Alternatives considered

- **Keep interval polling**: simple but wasteful and imprecise; the main design smell of v1.
- **External cron / systemd timers**: splits scheduling away from the bot process and complicates deployment.

## Consequences

- A full season schedules at most `matchdays × offsets × subscriptions` jobs (~114 today) in APScheduler's in-memory store — negligible.
- If the process restarts, jobs are rebuilt from the DB at startup; no persistent job store is needed.
- Timing accuracy is now APScheduler's (sub-second), not a ±30s window.
