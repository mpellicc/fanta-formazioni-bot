# ADR 0021: "Ho schierato" — silence remaining reminders once the lineup is set

- Status: accepted
- Date: 2026-07-14

## Context

Promoted from an unplanned v2.0 idea to v1.0 scope on 2026-07-14 (see
`docs/HANDOFF.md`): a way for the user to mark that, for the upcoming
matchday, the lineup is already set, so the *remaining* reminders for that
round stop arriving — they resume automatically at the next round, since
`reminders/planner.py` already plans per `(chat_id, round, offset)`.

The HANDOFF sketch assumed this could apply to any subscription (private,
group, channel). Working through it surfaced a correctness problem not
visible at sketch time: `subscriptions` is keyed by `chat_id`, not by user
(see `models.py::Subscription`, ADR 0008). A private chat is one person, one
team — "ho schierato" is unambiguous there. A **group or the official
channel is shared by several distinct fantacalcio managers**; if any single
member could silence the chat's reminders, everyone else who hasn't set
their lineup yet would silently stop being reminded. This is not a niche
edge case for this bot — the primary production subscriber
(@fantaformazionireminders) is exactly this shape.

A correct multi-user version (silence only once *every* manager in the chat
has confirmed) needs a roster of "who counts as a manager in this chat", which
the Bot API cannot supply (only chat administrators are enumerable, not
regular members). The only feasible approximation is a lazily-built roster —
a new `group_participants` table populated by whoever has ever pressed the
button — with silencing gated on all *known* participants confirming. This is
real, buildable work (new table, per-user confirmation tracking, "3/5
confirmed" UI, join/never-interacted edge cases) but is a materially bigger
feature than "small and self-contained", which was the explicit reason
Matteo brought this into v1.0 scope on 2026-07-14 instead of leaving it for
after. Decided in the design conversation preceding this ADR: **defer group
support to its own future ADR/session**, ship private chats only for v1.0.

## Decision

**"Ho schierato" is available only in private chats.** In groups and the
channel, the command replies that the feature isn't available there yet; no
button is attached to reminders sent to non-private chats.

**Surface**: both a standalone command and a button on reminder messages
(matching the rest of the bot: every subscription-affecting action has both
a command and an equivalent inline control — ADR 0012/0013/0015).

- `/ho_schierato` (no arguments): confirms the **next upcoming matchday**
  (same round `/prossima_scadenza` would report, via
  `planner.next_deadline`). No round argument — consistent with the rest of
  the bot, which never asks the user to name a round.
- Every reminder message sent to a private chat (`reminders/jobs.py::send_reminder_job`)
  carries a "✅ Ho schierato" inline button, scoped to that message's own
  `round` via `callback_data` — precise even if two rounds' reminders happen
  to be in flight at once (adjacent matchdays close together).
- Pressing it, or running the command, is **undoable**: the confirmation
  message/edited reminder shows a "↩️ Annulla conferma" button that clears
  the flag and lets the round's remaining reminders resume. Chosen over
  shipping one-way (Matteo: accidental taps should be recoverable without
  waiting for the deadline or a manual DB edit).

**Storage**: a new table, `lineup_confirmations (chat_id, round)`, same
shape as `sent_reminders`. Presence of a row = confirmed for that round.
Resets automatically for round N+1 since it's a new row — no explicit reset
logic needed.

**Effect on scheduling**: `reschedule_reminders` (`reminders/jobs.py`) skips
planned reminders whose `(chat_id, round)` is in `lineup_confirmations`, the
same way it already skips ones in `sent_reminders`. `send_reminder_job` gets
the identical guard as a second check (mirrors the existing
`was_reminder_sent` double-guard: reschedule filters proactively, the job
itself re-checks in case it was already in flight when the DB changed).
Confirming or undoing calls the existing `reschedule_reminders(application)`
— the same full drop-and-rebuild already used by
subscribe/unsubscribe/set_offsets — rather than introducing a new
targeted-cancellation helper; the codebase already treats this as cheap
enough given the subscriber count, and reusing it keeps the change smaller.

`reminders/planner.py` stays pure and unchanged: the confirmed-round filter
is DB-driven bookkeeping, applied in `jobs.py` alongside the existing
`sent_reminders` filter, not a concept the scheduling math itself needs to
know about.

`send_reminder_job` reads the subscription's `chat_type` (already fetched
per DB call, negligible at this volume) to decide whether to attach the
button, instead of threading `chat_type` through `PlannedReminder` — keeps
the pure planner's output shape unchanged and avoids touching the tests that
construct `PlannedReminder` directly.

## Alternatives considered

- **Full multi-user roster support in groups/channel now** — rejected for
  v1.0: real but disproportionate scope increase (new table, per-user
  tracking, roster bootstrap semantics, new UI) for a feature explicitly
  brought forward *because* it was supposed to stay small. Left as a future
  ADR.
- **Show the button everywhere, but no-op with an explanatory toast in
  groups/channel** — rejected: the channel is the bot's primary production
  surface with many subscribers; shipping a prominent button that always
  replies "not available here" there is worse UX than not showing it.
- **One-way confirmation (no undo)** — rejected per Matteo's explicit
  preference in the design discussion; the extra surface is one more table
  delete + two more messages, not a meaningful complexity jump.
- **Round as a command argument** (`/ho_schierato 7`) — rejected: no other
  command in this bot asks the user to name a round number, and the
  "next upcoming" default already covers the only case that matters day to
  day; the button path is unambiguous by construction anyway.

## Consequences

- New table `lineup_confirmations (chat_id INTEGER NOT NULL, round INTEGER NOT NULL, UNIQUE(chat_id, round))`,
  disposable like `sent_reminders` (worst case after loss: a round's
  reminders that were meant to be silenced fire again).
- New `Repository` methods: `mark_lineup_confirmed`, `unmark_lineup_confirmed`,
  `is_lineup_confirmed`.
- New command `/ho_schierato`; two new callback patterns
  (`lineup:confirm:`, `lineup:undo:`) in `telegram/keyboards.py` +
  `telegram/callbacks.py`.
- `reminders/jobs.py`: `reschedule_reminders` and `send_reminder_job` gain
  an extra DB-backed skip condition, following the exact shape of the
  existing `sent_reminders` one.
- No schema change to `subscriptions` or `matchdays`.
- Follow-up (not this ADR): BotFather command list on both bots needs
  `ho_schierato` added (operational step, tracked in `docs/HANDOFF.md`
  alongside the existing BotFather housekeeping notes).
- Group/channel support remains an open item for a future ADR, alongside
  the already-deferred user-owned channels idea — both need their own
  design session rather than being folded into this one.
