# ADR 0030: Product direction — v1.4, v1.5 and the road to v2.0

- Status: accepted
- Date: 2026-09-09

## Context

With v1.3 in production (event logging and the `bot_events` metrics table,
PRs #38/#39), the feature backlog inherited from `docs/HANDOFF.md` had grown
into a flat list of unranked ideas: user-owned league channels, a
dashboard/menu hub, inline mode, forum-topic-aware buttons, plus the frozen
live-updates research (ADR 0026).

This ADR is not a technical decision about a single component. It records the
**product direction** agreed in session on 2026-09-09: what the next minors
are for, what earns a major, and which questions must be answered before the
major can be designed. It exists so the next session does not re-derive the
ranking from scratch.

Two constraints framed the discussion:

- **The 2026-27 season is running.** Releases land while real users depend on
  the reminder path.
- **Risk appetite**: additive work *and* targeted refactors are acceptable
  in-season (with an ADR and tests), as long as the reminder engine
  (`reminders/planner.py`, `reminders/jobs.py`) stays intact.

## Decision

### 1. v1.4 — growth and adoption (in-season)

The goal of the next minor is **adoption**: making the bot easier to spread
beyond the official channel. Scope:

- **Forum-topic-aware buttons.** Close the known gap already documented in
  `docs/HANDOFF.md`: in a forum group with reminders already on, `/promemoria`
  only offers the off button, so there is no keyboard path to move delivery
  into a topic — the user is forced onto `/promemoria_on`, a legacy command
  (ADR 0018, Amendment 2026-07-10). `Chat.is_forum` plus `topic_thread_id()`
  are enough for `build_subscription_keyboard` to add a "send to this topic"
  button when the current topic differs from `subscriptions.message_thread_id`.
- **Onboarding and sharing.** A more explicit `/start`, deep links
  (`t.me/<bot>?start=…`), an "add me to your group" path, and a welcome
  message when the bot is added to a group.

Both are additive over existing surfaces and do not touch scheduling.

### 2. v1.5 — inline mode

**Inline mode ships separately from v1.4.** It is the strongest diffusion
lever (`@bot` in any chat shares the next-deadline card without adding the bot
anywhere), but it is a *new Telegram surface*: a BotFather setting, an
`InlineQueryHandler`, and its own manual test pass. Bundling it with v1.4
would make one release too large to test in a single in-season pass.

### 3. Metrics stay out of the bot

Adoption must be measurable, but **no `/stats` command and no metrics
reporting job will be added to the bot.**

Usage metrics are already served by `osservatorio-hq`, a separate local-only
single-user dashboard which reads this bot's SQLite database over
`ssh` + `docker exec` with read-only `SELECT`s.

The ideology is explicit: **the bot is a fully independent project and knows
nothing about osservatorio.** `bot_events` (ADR 0028/0029) is domain logging
the bot keeps for its own sake; that a dashboard happens to read it is
osservatorio's business. Consequently:

- New adoption metrics are added as *source metrics in osservatorio*, not as
  features here.
- The bot owes osservatorio no compatibility guarantee. If a schema change
  breaks a chart, osservatorio adapts — its adapter already degrades one
  metric at a time rather than failing the whole source.
- Rejected alternatives: stable SQL `VIEW`s as a read contract, and
  documenting event-type names as a public surface. Both would make the bot
  aware of a consumer it must not know about.

The only metrics-adjacent work allowed in the bot is emitting `bot_events`
rows for genuinely new domain actions (e.g. a deep-link start), on the same
grounds as every existing event: it is the bot logging its own domain.

### 4. What earns v2.0

A major is reserved for **breaking changes to the command/UX surface** and a
**change of domain**. The candidate content:

- **User-owned league channels** — the long-standing "next big feature". Moved
  out of the minors and into the major: it needs its own ADR, a
  `ChatMemberHandler(MY_CHAT_MEMBER)`, a BotFather "Channel Admin Rights"
  setting, and it still carries four open design questions (see the v2.0
  section of `docs/HANDOFF.md`).
- **Breaking command/UX cleanup** — e.g. retiring legacy commands, and a
  dashboard/menu hub that consolidates `/start` + `/promemoria` +
  `/personalizza_orari` instead of sitting beside them.
- **League companion** — the bot knowing a league (roster, auction/market
  deadlines, who has set their lineup), extending the roster introduced in
  ADR 0027.
- **Fanta-platform integration** — reading real deadlines and lineups from
  Fantacalcio.it / Leghe FC, feasibility unverified.

**Release window**: not necessarily end of season. v2.0 targets an
international-break window or early 2027, **by early February 2027** (before
the winter market closes) — a period when a breaking release disrupts users
least.

### 5. A feasibility spike precedes the v2.0 design

The league-companion and platform-integration strands both depend on data
sources we do not control. Before designing them, run a **dedicated research
session on available data sources** (official APIs, terms, cost), and record
the outcome in its own ADR **even if negative** — exactly as ADR 0026 did for
live match updates. The canonical failure mode is spending a design session on
a feature whose data turns out to be premium-only.

## Consequences

- The next planned work is the v1.4 pair (topic-aware buttons, onboarding),
  each ADR-first as usual; v1.5 (inline mode) follows as its own release.
- `docs/HANDOFF.md`'s idea list is now ranked by this ADR; where the two
  disagree, this ADR wins.
- User-owned channels stay designed-but-unbuilt for longer than previously
  planned. Accepted: the plumbing is already in place (`chat_type="channel"`,
  `origin='user'`, ADR 0008 + amendment), so the delay costs nothing but time.
- No analytics surface will accumulate in the bot, keeping its command list
  and its dependency graph focused on reminders.
- The v2.0 window is a target, not a commitment; if the feasibility spike
  comes back negative on both data-dependent strands, v2.0 narrows to
  channels + the breaking UX cleanup.
