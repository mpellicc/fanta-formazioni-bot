# ADR 0012: User and group subscription commands

- Status: accepted
- Date: 2026-07-07

## Context

ADR 0008 modeled reminder recipients as `subscriptions` rows and left per-user and
per-group reminders as "INSERTs plus new command handlers". This ADR fixes the
command surface and semantics for those handlers.

## Decision

Three commands operate on the subscription of the chat they are issued in:

- **`/promemoria_on`** — subscribe the current chat (`origin='user'`, default
  offsets from `REMINDER_OFFSETS`). If a subscription already exists the command
  only confirms it: it never overwrites `reminder_offsets`, so future custom
  times survive a repeated `/promemoria_on`.
- **`/promemoria_off`** — delete the subscription. Only `origin='user'` rows are
  deletable by command; the env-seeded channel row is owned by config (ADR 0008
  amendment) and stays untouched. `sent_reminders` rows are kept, so
  unsubscribing and resubscribing within the same matchday cannot duplicate
  reminders.
- **`/promemoria`** — show whether reminders are active in the chat and with
  which offsets.

In groups and supergroups, `/promemoria_on` and `/promemoria_off` are restricted
to **group administrators**: the sender must be an anonymous admin (message sent
on behalf of the group itself, `sender_chat == chat`) or have chat member status
`administrator`/`creator` via `get_chat_member`. Private chats have no
restriction; `/promemoria` (read-only) is open to everyone.

Channels are out of scope: channel posts are not command messages, so the
channel subscription remains config-managed.

## Alternatives considered

- **Anyone in the group can toggle**: no extra API call, but any member could
  silence the whole league's reminders; one `get_chat_member` call per command
  is negligible at this traffic.
- **Overwrite offsets on repeated subscribe**: simpler upsert, but would reset
  the custom times of roadmap feature #2 as a side effect of an idempotent-looking
  command.
- **Soft-delete (active flag) instead of DELETE**: keeps history nobody needs;
  dedupe already lives in `sent_reminders`, which survives the DELETE.

## Consequences

- The reminder engine, planner, and startup pruning are unchanged; subscribing
  or unsubscribing just triggers the existing `reschedule_reminders`.
- Custom per-subscription times (roadmap #2) only need a command that updates
  `reminder_offsets` on the existing row.
- The BotFather command list must be updated manually with the three commands.
