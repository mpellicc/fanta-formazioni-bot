# ADR 0025: Delivering reminders to the forum topic a subscription was activated in

- Status: accepted
- Date: 2026-08-28

## Context

Telegram supergroups can turn on **topics** (forum mode): a chat that is really
several threads, each with its own `message_thread_id`. `subscriptions`
(`storage/repository.py`) stores only `chat_id`/`chat_type`, and
`send_reminder_job` (`reminders/jobs.py`) sends with `chat_id` alone — there is
no `message_thread_id` anywhere in `src/` or `tests/`. Telegram routes a plain
send-by-`chat_id` to the forum's "General" topic, never to the topic a fantalega
actually uses. A user already asked for this, so it needs closing quickly.

**Goal**: when `/promemoria_on` / `/personalizza_orari` (command or button) is
run *inside a topic*, reminders for that chat are delivered to that topic;
running the same command in a different topic moves delivery there. The bot's
confirmation reply is itself the proof it worked — being a `reply_text`, it
lands in the topic the command was run from.

## Decision

- **One subscription per chat**, with an optional destination topic. The
  primary key of `subscriptions` stays `chat_id`: no impact on
  `sent_reminders`, `lineup_confirmations`, `PlannedReminder`, `planner.py`, or
  job names. ADR 0008 is unaffected.
- **Implicit binding, no new command.** The topic is whichever one the message
  or callback that (re-)activates the subscription happened to be posted in,
  read via `Message.is_topic_message` / `Message.message_thread_id`. A helper,
  `telegram/commands.py::topic_thread_id(message)`, centralizes the read and
  the "General" special case: in forums, messages in "General" have
  `is_topic_message = False`, so the thread id must be treated as `None` there
  too — otherwise the very first message in the chat's default topic would
  wrongly pin delivery to it.
- **No topic name stored or shown.** python-telegram-bot 22.x has no
  `getForumTopic` call (only `get_forum_topic_icon_stickers`), so a name would
  only be recoverable partially and with real extra plumbing. Out of scope: the
  confirmation stays generic ("Li manderò solo in questo topic."), it does not
  name the topic.
- **Re-running the activating command moves the binding.** `subscribe()` no
  longer returns early on `already_subscribed` without checking anything: it
  compares the topic the message was sent from against the stored one and, if
  different, updates it (`update_subscription_thread`). It does **not**
  reschedule: `PlannedReminder` carries no thread id and `send_reminder_job`
  re-reads the subscription at send time, so a destination change needs no job
  churn. Reminder offsets are never touched by this path (ADR 0019/0020's
  invariant holds): only the destination can change on an existing
  subscription.

## Alternatives considered

- **Composite key `(chat_id, message_thread_id)`, one row per topic**: would
  let a group fan out reminders to several topics from several subscribes.
  Nobody asked for that, and it multiplies every join/query in
  `storage/repository.py` and the planner's chat iteration (ADR 0008) for a
  case with no known user. Rejected as premature.
- **A dedicated command (e.g. `/promemoria_qui`) to (re)bind the topic**: adds
  a command surface and a decision point ("which command do I run?") for
  something the existing activation flow already captures implicitly for
  free. Rejected.
- **Naming the topic in the confirmation**: blocked by the Bot API gap noted
  above; would need caching a name observed once from an unrelated event
  (e.g. a forum-topic-created update) with no guarantee of staying current.
  Rejected as out of scope.

## Consequences

- `subscriptions` gains a nullable `message_thread_id INTEGER`, migrated the
  same way `origin`/`created_at` were (ADR 0022): existing rows get `NULL`,
  meaning "no topic pin, deliver as today".
- `SubscribeResult` gains `topic_changed: bool` and `set_offsets` now returns a
  `SetOffsetsResult` instead of a bare bool, so command/callback handlers know
  whether the destination moved — in **either** direction. Both activation paths
  can move it, and running the command from "General" un-binds a previously
  pinned topic, so leaving that silent would change where reminders land with no
  word to the user. `topic_suffix()` turns the flag plus the thread id into the
  right fragment (`subscription_topic_bound` / `subscription_topic_unbound`), or
  "" on a plain re-run from the same place.
- `send_reminder_job` passes `subscription.message_thread_id` straight through
  to `send_message`; a closed topic or a topic deleted after binding is a
  transient/unwritable error already handled by `telegram/errors.py`
  (ADR 0023) — it does not prune the subscription, it just fails that one send.
- No new row in `subscription_events` (ADR 0024): moving a topic is a
  destination change, not a lifecycle event (subscribe/unsubscribe/dead_chat).
- Non-forum groups, channels, and private chats are unaffected:
  `topic_thread_id` returns `None` for them, so `message_thread_id` stays
  `NULL` and delivery is exactly as before this ADR.
