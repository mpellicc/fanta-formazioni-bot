# ADR 0023: Pruning subscriptions whose chat can no longer be written to

- Status: accepted
- Date: 2026-08-27

## Context

`error_handler` (`telegram/errors.py`) stopped reporting undeliverable-destination
errors to the debug chat (PR #30): a closed forum topic or a chat that blocked
the bot is not a code defect, and a stacktrace per occurrence is noise nobody
can act on.

That is correct for one-off replies, where the chat is by definition interacting
with us and the next command simply succeeds. It is not enough for reminders.
`send_reminder_job` (`reminders/jobs.py`) writes to a chat that may have kicked
or blocked the bot weeks earlier, and nothing observes the failure: the row stays
in `subscriptions`, the planner (ADR 0008) keeps producing reminders for it, and
every one of them fails. Three offsets × every matchday × the rest of the season,
silently, with `mark_reminder_sent` never reached — so not even the dedupe table
records the attempt.

The information needed to act — *which* chat is gone — exists at the send site
and nowhere else. `error_handler` receives an exception, not a `chat_id`.

Two failure modes look alike but are not:

- **Terminal**: the bot was blocked, kicked, or removed; the user is deactivated;
  the chat no longer exists. No message will ever be delivered again unless the
  chat re-subscribes.
- **Transient**: the forum topic the message would land in is closed, or a
  permission was revoked in a chat we are still a member of. The chat may well
  accept the next reminder.

## Decision

Classify at the send site and act on the terminal case only.

- `telegram/errors.py` grows `is_dead_chat_error(error)`: every `Forbidden`
  (blocked, kicked, not a member, deactivated user) plus `BadRequest: chat not
  found`. `is_unwritable_chat_error` — the "do not report to the debug chat"
  predicate — is now defined as `is_dead_chat_error` **or** a transient
  condition (`Topic_closed`, `topic_deleted`, `message thread not found`,
  revoked send rights). Dead is a strict subset of unwritable: everything
  terminal is also unreportable, not everything unreportable is terminal.
- `send_reminder_job` wraps its `send_message`. On a dead-chat error it calls
  `_prune_dead_chat`; every other exception propagates to `error_handler`
  unchanged.
- `_prune_dead_chat` branches on `Subscription.origin` (ADR 0008):
  - `origin='user'` → `delete_user_subscription`, and every still-pending
    reminder job for that `chat_id` is cancelled by name prefix
    (`reminder:{chat_id}:`), the same mechanism `reschedule_reminders` uses.
    Logged at WARNING; **not** reported to the debug chat. A user blocking the
    bot is ordinary churn, not an incident, and `/promemoria_on` re-creates the
    row (with a fresh `created_at`, ADR 0022) whenever they come back.
  - `origin='env'` → the row is **kept** and the failure **is** reported to the
    debug chat. That row is the configured `CHANNEL_CHAT_ID`, re-seeded by
    `_post_init` on every restart (ADR 0010), so deleting it would be undone at
    the next deploy and the failure would repeat forever. The bot losing access
    to the channel it exists to serve is exactly the incident the debug chat is
    for, and it is the one case where a human must intervene.
- A transient error still reaches `error_handler`, which logs it and stays
  quiet. The reminder for that offset is lost — deliberately: it is not
  re-queued, since by the time the topic reopens the deadline has likely passed
  and a late reminder is worse than none.

`reminders/planner.py` stays pure and unchanged: pruning is I/O, so it lives in
`jobs.py`.

## Alternatives considered

- **Mark the row dead (a `disabled_at` column) instead of deleting it**: keeps
  the analytics trail (ADR 0022) and would let the bot notice a chat coming
  back. Rejected for now: every read path (`get_subscriptions`,
  `get_subscription`, the planner's input) would need to filter on it, and a
  chat that unblocks the bot has no way to signal that other than sending a
  command — which already re-subscribes it. Deletion keeps `subscriptions`
  meaning exactly "chats that receive reminders".
- **Treat any unwritable error as terminal**: one closed topic would unsubscribe
  an active group that never asked to leave. Rejected — this is precisely the
  distinction the ADR exists to draw.
- **Report user-subscription pruning to the debug chat too**: turns normal churn
  into a notification stream and re-creates, in a different shape, the noise PR
  #30 removed. Rejected; the WARNING log is the record.
- **Delete the env channel row as well**: `_post_init` re-seeds it on the next
  restart, so the delete is silently reverted and the loop resumes. Rejected.
- **Retry the failed reminder later**: a dead chat cannot be retried into
  existence, and for the transient case a reminder delivered after the deadline
  is actively misleading. Rejected.

## Consequences

- `subscriptions` shrinks on its own. A chat that blocks the bot disappears from
  the growth numbers (ADR 0022) with no record that it ever left — the dashboard
  sees the row vanish, not an unsubscribe event.
- A user who blocks and later unblocks the bot gets no reminders until they send
  `/promemoria_on` again. Their `created_at` resets, so they count as a new
  subscriber.
- The debug chat now receives a message per failed reminder to the env channel
  (at most one per configured offset per matchday) instead of a stacktrace per
  failure. Not deduped, matching the staleness alert's reasoning (ADR 0014): the
  volume is bounded and the condition is one a human must clear anyway.
- `errors.py` owns the vocabulary for "Telegram refused this destination", and
  `jobs.py` depends on it. Any new send site that needs the distinction imports
  the same two predicates rather than re-deriving them from error strings.
