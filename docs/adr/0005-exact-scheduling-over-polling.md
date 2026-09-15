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

## Amendment (2026-09-15): the reminder text states the nominal offset

Sub-second scheduling accuracy exposed a defect on the *display* side. `send_reminder_job`
measured the remaining time against the system clock at the instant the job ran, and
`format.format_remaining` truncates with `int()`: firing a few milliseconds after
`deadline − offset` made every reminder announce one unit less than it should — "59 minuti"
for the 1h offset, "4 minuti" for the 5m one, "23 ore e 59 minuti" for the 24h one. No
delivery delay was involved; APScheduler's default `misfire_grace_time = 1` (PTB does not
override it) skips a job that is more than a second late rather than running it late, so
genuine lateness would show up as a *missing* reminder, not a shifted one. Measured on the
production DB (round 4, the 5m reminder, every subscription): `bot_events.occurred_at`
lands 0.13s to 0.32s after the planned instant, inside the same second, with the VM clock
NTP-synchronised. The delay was never real; only the arithmetic was.

The reminder is now formatted against its planned instant (`deadline − offset_seconds`),
which by construction is the same value `planner.plan_reminders` scheduled it at, so the
text states exactly the subscription's offset. That substitution holds only within
`SCHEDULING_TOLERANCE` (5s): beyond it the lateness is real, or the deadline moved after the
job was scheduled, and the wall clock wins — a late reminder must still tell the truth, and
the message must not depend on a library default to make lateness impossible.

`format_remaining` keeps truncating: for an on-demand countdown (`/prossima_scadenza`, the
inline card) that is the correct semantics, and rounding up would overstate the time left
before a deadline, which is the worse of the two errors.

The mock provider (ADR 0016) now returns a kickoff truncated to the whole minute, like both
real providers, so a dev test run reproduces production timing instead of landing on a random
second of the minute.
