# ADR 0016: Mock calendar provider for pre-season reminder testing (dev only)

- Status: accepted
- Date: 2026-07-07

## Context

The 2026-27 season starts 2026-08-22 (`docs/HANDOFF.md`); until then, every
real matchday's deadline is weeks or months away, so the actual `run_once`
reminder path (ADR 0005) — a job firing, sending the message, recording
`sent_reminders` — has never been exercised end-to-end, only its command
surface. ADR 0007 made the calendar source pluggable specifically so a new
source could be added "as a new module + a factory entry"; this ADR uses that
same seam to add a third, test-only provider that fabricates a matchday a few
minutes from now, so the dev bot can be made to fire a real reminder on
demand.

## Decision

**1. New enum member: `CalendarProvider.MOCK = "mock"`** (`config.py`),
alongside `FIXTUREDOWNLOAD`/`FOOTBALL_DATA_ORG`.

**2. New provider: `calendar/mock.py`.**

```python
class MockProvider:
    def __init__(self, kickoff_offset: timedelta) -> None:
        self._kickoff_offset = kickoff_offset

    async def fetch_matchdays(self) -> list[Matchday]:
        return [Matchday(round=1, kickoff=datetime.now(UTC) + self._kickoff_offset)]
```

Returns a **single** `Matchday`, computed fresh relative to "now" on every
call — so every refresh (the daily job, or a bot restart, which calls
`refresh_calendar` in `_post_init`) produces a new near-future kickoff,
letting you re-trigger a test just by restarting the dev bot, no manual DB
edits needed.

It reuses **round 1** rather than a synthetic round number. `upsert_matchdays`
only does `INSERT ... ON CONFLICT DO UPDATE` (`storage/repository.py`), never
deletes rows a provider stops returning — so a made-up round would linger in
the `matchdays` table forever after switching back off mock. Round 1 is
already the row fixturedownload/football-data.org populate for the real
season opener; the next refresh from the real provider simply overwrites its
`kickoff_utc` back to the true value via the same `ON CONFLICT`, leaving no
trace.

**3. New setting: `mock_kickoff_offset: timedelta = timedelta(minutes=10)`**,
parsed from env the same way as `deadline_margin` (reusing `parse_duration`,
same `field_validator` pattern). Lets you widen or shrink the test window
(e.g. `2g,12h,10m`-style combos via `/personalizza_orari` custom offsets, see
Consequences) by changing one GitHub environment variable and redeploying,
with no code change.

**4. Factory wiring** (`calendar/base.py::create_provider`):

```python
case CalendarProviderName.MOCK:
    return MockProvider(settings.mock_kickoff_offset)
```

**5. Deploy pipeline**: `MOCK_KICKOFF_OFFSET` is added as an optional,
**per-environment** GitHub variable (like `CALENDAR_PROVIDER`, not a
repo-level secret like `FOOTBALL_DATA_API_KEY` — it's a per-environment
tuning knob, not a shared credential), defaulting to `10m` when unset,
following the exact pattern `deploy.yml` already uses for `CALENDAR_PROVIDER`.

**6. No code-level guardrail against using `mock` in production.** Same
discipline as `CALENDAR_PROVIDER` itself (ADR 0007/0014): it is always a
manual admin choice, applied by setting the GitHub environment variable and
redeploying (ADR 0010) — never automatic, never inferred from other config.
The only safeguard is documentation: `docs/DEPLOY.md` gets an explicit "never
set `CALENDAR_PROVIDER=mock` on the `production` environment" note next to
the existing per-environment variable table.

## Alternatives considered

- **Hardcoded offset in `MockProvider`** instead of a new setting: zero new
  config/deploy.yml surface, but every change to the test window needs a code
  change + commit + redeploy, instead of updating one GitHub variable +
  redeploy — strictly worse for something meant to be tuned repeatedly while
  testing.
- **Two mock matchdays** (near + far) to also exercise "pick the soonest,
  then roll to the next after it fires": more faithful to real multi-round
  behavior, but doubles the state the provider has to fabricate for a
  question (does `next_deadline`/`plan_reminders` correctly pick the
  minimum?) already covered by `tests/test_planner.py` against real data.
  Single matchday is enough to exercise the part that's never actually run:
  a `run_once` job firing and a reminder being sent.
- **Manually editing the `matchdays` table on the dev bot**: no code at all,
  but the daily refresh job (02:00) or any restart immediately overwrites it
  with real (far-future) data — the edit doesn't survive, so every test
  session would need re-editing the DB by hand.
- **Code-level guardrail** (e.g. refuse `mock` unless some `IS_DEV` flag is
  also set): rejected — it would be the only calendar provider with an
  enforced usage restriction, inconsistent with how `CALENDAR_PROVIDER` is
  treated everywhere else, for a misconfiguration that's already unlikely
  (config is pipeline-managed per ADR 0010, never hand-edited on the VM).

## Consequences

- Testing a reminder end-to-end: set the `development` environment's
  `CALENDAR_PROVIDER=mock` (and optionally `MOCK_KICKOFF_OFFSET`), redeploy,
  then use `/personalizza_orari` on the chat under test to pick short custom
  offsets (e.g. a few minutes apart) so more than one reminder fires within
  the mock window — no new mechanism needed there, it's the existing
  ADR 0013 feature. Switch `CALENDAR_PROVIDER` back to `fixturedownload`
  afterwards and redeploy; the next refresh restores the real round 1
  kickoff.
- `calendar/base.py::create_provider` gets a third `case`, same shape as the
  other two — matches ADR 0007's stated extension cost exactly.
- `env.example` and `docs/ARCHITECTURE.md`'s provider/env-var docs mention the
  new value and setting.
