# ADR 0026: Live match updates deferred — no free source covers goal events

- Status: rejected (for now)
- Date: 2026-08-31

## Context

A "live match updates" feature was scoped as a possible addition to the bot:
during a matchday, push **kick-off, goals and full-time** to subscribed chats,
toggleable from an inline button (or a legacy command, per ADR 0018's
legacy/promoted convention).

Four parameters were chosen up front, before any research:

- **Coverage**: the whole matchday — all 10 Serie A fixtures, no per-user
  fixture selection.
- **Delivery**: hybrid — one live board per slot, edited in place via
  `editMessageText`, plus a separate push message for each goal (so the goal
  still produces a notification, without the board spamming the chat).
- **Data source**: **official free APIs only** — no scraping, no undocumented
  endpoints, no paid plan.
- **Latency**: ~1 minute for a goal.

The research question was whether that is buildable on our infrastructure for
free or near-free. The answer is **no** — and the blocker is not our
infrastructure.

## Decision

**Freeze the feature.** Implement nothing; record why, so this research is not
repeated.

**Our side is not the constraint.** A PTB job polling once a minute during the
live windows is negligible for the Oracle Always Free VM (1 GB), the extra
state fits the existing `subscriptions` + dedupe-table pattern (ADR 0008 /
0005), and the hybrid delivery stays inside Telegram's rate limits. The blocker
is **data availability**.

| Source | Live? | Cost | Verdict |
| --- | --- | --- | --- |
| football-data.org — Free (**already integrated**, `calendar/football_data_org.py`) | ❌ "Scores delayed", 10 calls/min, Serie A included | €0 | Free-tier scores are delayed by policy: unusable for live |
| football-data.org — "Free w/ Livescores" | ✅ live scores, 20 calls/min | €12/mo | Enough for kick-off/goal/full-time, but **no scorer** |
| football-data.org — Standard | ✅ + goal scorers, bookings, line-ups | €49/mo | Out of scale |
| api-football (api-sports) — Free | ✅ full events, 15s refresh | €0, but **100 requests/day** | ~600 minutes of fixtures on a full Sunday → one poll every ~6 min. Incompatible with the ~1 minute target |
| api-football — Pro | ✅ full events | $19/mo, 7,500 req/day | Outside the "free" constraint |
| TheSportsDB — Free | ❌ livescores are premium-only | $9/mo for 2-minute livescores | 2 minutes, not 1 |

**The structural constraint worth remembering**: a goal *with scorer and
minute* is a premium data-point everywhere. Below €49/mo the best obtainable is
detecting a goal as a **score delta between two polls** — "⚽ Inter 1-0 Milan
(23')" with no name attached. For a fantacalcio bot that is a substantive
limitation, not a cosmetic one: the player's name is precisely what a
fantallenatore cares about.

**Three ways out of the constraint** — none chosen, all still open:

1. **€12/mo** (football-data.org "Free w/ Livescores") — by far the shortest
   implementation path: same provider already integrated, same API key, same
   `httpx` client; only the endpoint changes
   (`/v4/competitions/SA/matches?status=LIVE`) plus score diffing. Goals
   without scorer.
2. **Undocumented endpoints / scraping** — free, rich events including the
   scorer, low latency; in exchange, fragility (breaks without warning, quite
   possibly mid-Sunday), a grey area on terms of service, and it becomes the
   most expensive part of the bot to maintain.
3. **api-football free, ~6 minute latency** — €0 with full events, but the
   updates land after the notifications users already have on their phone.

## Consequences

- **No impact on the current codebase**: no code, no dependency, no env var, no
  table. `calendar/football_data_org.py` keeps doing exactly what it does today
  (fetching the season's matchdays — ADR 0007/0014).
- Reopen this decision if the budget changes, or if a goal **without** the
  scorer's name is accepted as good enough — in that case option 1 is small and
  well understood.
- **Technical note, reusable if this thaws**: football-data.org's `status`
  exposes the workflow `SCHEDULED → TIMED → IN_PLAY → PAUSED → FINISHED` (plus
  `SUSPENDED`/`POSTPONED`/`CANCELLED`/`AWARDED`), and the pseudo-value `LIVE`,
  usable as a filter, combines `IN_PLAY`+`PAUSED`. Kick-off and full-time are
  therefore **status transitions**, not dedicated events — readable even
  without the "goal scorers" data-point.
