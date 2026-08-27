# ADR 0024: `subscription_events`, distinguishing inactive from lost chats

- Status: accepted
- Date: 2026-08-27

## Context

`subscriptions` is the active set: a row means "this chat gets reminders". Both
ways of leaving delete the row — `/promemoria_off` (ADR 0012) and the dead-chat
pruning of ADR 0023 — so leaving is invisible. The consumer of ADR 0022
(*osservatorio-hq*, which reads this SQLite file directly, read-only) can count
who is subscribed now and, via `created_at`, when they joined; it cannot count
who left, or tell the two departures apart.

They are not the same departure, and the split is the point:

- `/promemoria_off` — the chat is still a user of the bot. It kept the bot
  around, it just doesn't want reminders. **Iscritto ma non attivo.**
- blocked, kicked, chat gone — the chat is no longer reachable at all and only
  a fresh `/promemoria_on` from their side can undo it. **Cancellato.**

ADR 0022 rejected a history table as "unwarranted for a single 'when did this
row first appear' question". That question has grown: the metric now spans a
state machine over time, which is exactly the case that ADR left open.

## Decision

Add an append-only `subscription_events` table. `subscriptions` keeps its
current meaning and its current read paths — **no query in the bot changes**.

```
subscription_events (id INTEGER PK AUTOINCREMENT, chat_id, chat_type, origin,
                     event TEXT, occurred_at TEXT)   -- + index (chat_id, occurred_at)
```

Three event kinds, written by `storage/repository.py` (all SQL stays there):

| `event`        | written by                                   | dashboard state          |
|----------------|----------------------------------------------|--------------------------|
| `subscribed`   | `upsert_subscription`, on a real insert only  | attivo                   |
| `unsubscribed` | `delete_user_subscription` (`/promemoria_off`)| iscritto, non attivo     |
| `dead_chat`    | `prune_dead_subscription` (ADR 0023)          | cancellato               |

- The event row is written **inside the same transaction** as the
  `subscriptions` change it describes: the log cannot disagree with the table.
- `upsert_subscription` records `subscribed` only when no row existed. It is
  called on every restart for the env channel (`_post_init`, ADR 0010) and
  `/promemoria_on` is idempotent; logging every call would invent subscribers.
- A delete that matches no row — a missing chat, or the `origin='env'` filter
  refusing the delete — records nothing. There was no leaving.
- `delete_user_subscription` and `prune_dead_subscription` are two thin wrappers
  over one private method, differing only in the event they log, so the two call
  sites cannot drift.
- `prune_channel_subscriptions` (the env channel replaced after a
  `CHANNEL_CHAT_ID` change) writes **no** event: that is a config edit, not a
  chat leaving, and counting it as churn would misattribute an ops action to a
  user.
- Current state per chat is `subscriptions` for "attivo" and the latest event
  for everyone else. The bot never reads the table.

## Alternatives considered

- **`deactivated_at` column on `subscriptions` (soft delete)**: simpler
  migration, but every read path (`get_subscriptions`, `get_subscription`, the
  planner's input) would have to filter it, and missing one means reminding a
  chat that left — a user-visible bug traded for a metric. It also keeps only
  the latest transition, losing repeated leave/rejoin cycles. Rejected.
- **One `left` event with a reason column**: same data, but the dashboard would
  have to know which reason values map to which of the two states. Distinct
  event names put that meaning in the log itself. Rejected.
- **Deriving churn from `created_at` gaps or `sent_reminders`**: guesswork from
  side effects; a chat that never had a reminder due is indistinguishable from
  one that left. Rejected.
- **Keeping the ADR 0023 behaviour (delete, no trace)**: the shrinking row count
  was already flagged there as a cost; this ADR pays it.

## Consequences

- `subscription_events` joins `subscriptions` as a table *osservatorio-hq* reads
  directly, so its column names and the three `event` values are now an external
  contract, with the same caveat ADR 0022 attached: nothing in this repo enforces
  it. Adding a new event kind is safe; renaming or repurposing one is breaking.
- The table only grows, and it grows with lifecycle changes rather than with
  traffic — a handful of rows per chat over a season. No retention policy for
  now; if one becomes necessary the aggregates must be rolled up before pruning,
  or the history it exists to hold is lost.
- Chats subscribed before this migration have no `subscribed` event. As with
  ADR 0022's `NULL` `created_at`, that is deliberate: they are "active since
  unknown", and the dashboard must not read a missing event as "never joined".
- A chat that unsubscribes and re-subscribes produces a full event trail, while
  its `subscriptions.created_at` resets on the new `INSERT` (ADR 0022). Where the
  two disagree, the event log is the one that reflects history.
- `dead_chat` counts only chats the *reminder* path found unreachable. A user who
  blocks the bot and never had a reminder due stays "attivo" until one fires.
