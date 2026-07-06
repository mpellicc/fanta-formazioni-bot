# ADR 0008: Subscription-based reminder model (future users/groups/custom times)

- Status: accepted
- Date: 2026-07-06

## Context

Today reminders go to a single Telegram channel configured via env. The roadmap includes private per-user reminders, per-group reminders, and per-subscriber custom reminder times — none implemented yet, but the architecture must not require a redesign when they arrive.

## Decision

Model reminder recipients as rows in a `subscriptions` table (`chat_id`, `chat_type`, `reminder_offsets` as JSON), and make the reminder engine iterate over subscriptions rather than a single hardcoded chat. At startup, the channel from `CHANNEL_CHAT_ID` is upserted as the one subscription, with offsets taken from the `REMINDER_OFFSETS` env setting (default `24h,1h,5m`).

Sent-reminder dedup is keyed per subscription: `sent_reminders(chat_id, round, offset_seconds)`.

## Alternatives considered

- **Single channel hardcoded in the engine**: simplest today, but per-user/group reminders would touch the engine, the schema, and the dedup logic later.
- **Full subscription commands now** (/subscribe etc.): scope creep; explicitly out of v2.

## Consequences

- Future features become INSERTs plus new command handlers; the engine and schema don't change.
- Reminder offsets are already per-subscription in the data model; the env value only seeds the default channel row.
