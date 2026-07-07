# ADR 0014: football-data.org as pluggable provider + fixturedownload staleness alert

- Status: accepted
- Date: 2026-07-07

## Context

Before the v2 rewrite, fixturedownload occasionally didn't update a round's
kickoff time until close to the deadline, leaving placeholder times
(`00:00` UTC, see `docs/HANDOFF.md`) in the CSV. ADR 0007 made the calendar
source pluggable (`CalendarProvider` protocol + `CALENDAR_PROVIDER` factory)
specifically so a second source could be added later "as a new module + a
factory entry" without touching the engine. This ADR exercises that path and
adds the missing piece: a way to notice staleness before it affects a
deadline, since there was previously no signal at all — fixturedownload
exposes no reliable "data last updated" metadata, only the content itself
(placeholder times).

football-data.org (docs: https://docs.football-data.org/general/v4/) was the
alternative already named in ADR 0007. Its `Competition Match List`
subresource (`GET /v4/competitions/{code}/matches`) returns each match's
`matchday` (round) and `utcDate` (kickoff, UTC) — a direct match for our
`Matchday(round, kickoff)` model. Auth is a single `X-Auth-Token` header;
Serie A's competition code is `SA`. The free registered tier allows
10 requests/minute, far more than the one request/day this bot needs.

## Decision

**1. `CalendarProvider` becomes a `StrEnum`, not a bare string.**

```python
class CalendarProvider(StrEnum):
    FIXTUREDOWNLOAD = "fixturedownload"
    FOOTBALL_DATA_ORG = "football-data-org"
```

Values are unchanged from today's string (`"fixturedownload"`), so existing
deployments need no config change. Pydantic validates the value at startup
instead of failing later inside the factory `match`.

**2. New provider: `calendar/football_data_org.py`.**

- `FootballDataOrgProvider(api_key: str)`, implementing the same
  `fetch_matchdays() -> list[Matchday]` protocol as `FixtureDownloadProvider`.
- Calls `GET https://api.football-data.org/v4/competitions/SA/matches` with
  `X-Auth-Token: {api_key}` and `season={season_year(now)}`; the Serie A code
  is hardcoded (this bot is Serie A-only everywhere else — channel name,
  texts — there's no real case for making it configurable).
- Maps each match's `matchday`/`utcDate` to `Matchday`, keeping the earliest
  kickoff per round (mirrors `parse_matchdays`' dedup logic in
  `fixturedownload.py`, since a round can have multiple fixtures).
- `season_year(now)` (currently private to `fixturedownload.py`) moves to
  `calendar/base.py` so both providers share the July-1st rollover rule
  (ADR 0007 consequence) without duplicating it.

**3. New setting: `FOOTBALL_DATA_API_KEY: str | None = None`.**

Optional at the `Settings` level (most deployments stay on fixturedownload
and never set it); the factory (`calendar/base.py::create_provider`) raises
`ValueError` if `CALENDAR_PROVIDER=football-data-org` and the key is missing
— same fail-fast style as the existing `case unknown` branch.

**4. Staleness alert on the existing daily refresh.**

After `refresh_calendar` fetches and upserts matchdays (`reminders/jobs.py`),
it checks the same "next upcoming matchday" used for reminders
(`planner.next_deadline`): if its deadline is within **3 days** and its
kickoff time-of-day is exactly `00:00` UTC (the known placeholder marker),
send a message to `DEBUG_CHAT_ID` naming the round and suggesting a review of
`CALENDAR_PROVIDER`. The alert text lives next to `errors.py`'s style
(English, technical — it's an operator message, not user-facing Italian
text bound by the `messages.py` convention).

Three days balances false positives (placeholder times are normal for
far-future rounds) against reaction time (redeploy with a new
`CALENDAR_PROVIDER` before the first default reminder offset, 24h before
deadline, would fire).

No dedup: the check re-runs on every refresh (daily, plus once at startup)
and re-sends the alert every time the condition still holds. At this
frequency, sent only to the private debug chat, a repeated nudge is more
useful than the extra code a per-round "already alerted" flag would need.

**Switching stays manual.** The alert does not trigger an automatic
provider switch: `CALENDAR_PROVIDER` is still an admin decision applied by
changing the env var and redeploying (ADR 0007), so a wrong staleness
signal can never silently swap the data source the whole system trusts.

## Alternatives considered

- **Generic `CSV`/`API` role naming instead of vendor-named enum members**:
  considered and rejected — nothing in the codebase reasons about providers
  by transport mechanism (the factory matches on identity, not "kind", and
  switching stays manual/vendor-specific), so the extra indirection wouldn't
  pay for itself and wouldn't generalize past two providers.
- **HTTP `Last-Modified`/`ETag` based staleness check**: reflects when
  fixturedownload's file was last regenerated, not whether the *content* for
  an upcoming round is still a placeholder; a file can be legitimately
  unchanged for days. Content-based detection (the `00:00` marker) is the
  only signal that actually correlates with the failure mode we saw.
- **Automatic failover to football-data.org on staleness**: rejected in
  discussion — needs reconciling two data sources, is a much larger surface
  for a bug (a wrong staleness signal would silently change the trusted
  source), and contradicts ADR 0007's explicit "admin decision, not
  automatic" framing.
- **Track per-round alert state to dedupe**: extra table/column for a
  spam problem that doesn't really exist at 1 alert/day into a private chat.

## Consequences

- Adding the third provider (if ever needed) means one more enum member,
  one more module, one more `case` in the factory — unchanged from ADR 0007.
- `season_year` becomes shared code in `calendar/base.py` instead of
  fixturedownload-specific.
- Switching to football-data.org in an emergency requires: set the
  per-environment `CALENDAR_PROVIDER` variable to `football-data-org` on the
  relevant GitHub environment, redeploy (ADR 0010). `FOOTBALL_DATA_API_KEY` is
  a **repository-level** secret, not per-environment: it's one football-data.org
  account/key shared by both bots, same reasoning as `SSH_HOST`/`SSH_USER`/`SSH_KEY`
  (one shared resource, not per-environment config that happens to coincide).
  `deploy.yml` writes both into the generated `.env`, defaulting
  `CALENDAR_PROVIDER` to `fixturedownload` when the variable is unset so
  existing deployments are unaffected.
- The staleness alert only covers the one failure mode we've actually seen
  (placeholder kickoff close to deadline); it says nothing about other ways
  a provider could misbehave.
