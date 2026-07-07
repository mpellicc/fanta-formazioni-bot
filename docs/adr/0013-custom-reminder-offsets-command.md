# ADR 0013: Custom reminder offsets via `/personalizza_orari`

- Status: accepted
- Date: 2026-07-07

## Context

ADR 0008 made `reminder_offsets` a per-subscription field and left custom times
as "a command that updates `reminder_offsets` on the existing row". ADR 0012
fixed `/promemoria_on` to never overwrite offsets specifically so this feature
could land without resetting them. This ADR fixes the command surface,
grammar, and validation.

## Decision

**`/personalizza_orari`** sets the reminder offsets of the chat it is issued
in:

- **With arguments** (`/personalizza_orari 24h 1h 5m`, space- and/or
  comma-separated): parses each token with the existing `parse_duration`
  (`s`/`m`/`h` units), validates the result, and writes it to
  `reminder_offsets` on the chat's subscription.
  - Each offset must be between **1 minute and 7 days**.
  - **Max 10** offsets; duplicates are dropped; the stored list is sorted
    descending (soonest-last, matching the existing default ordering).
  - If the chat has no subscription yet, one is created (`origin='user'`,
    `chat_type` from the update) — setting offsets implies wanting reminders,
    so this doubles as subscribing.
  - Invalid input (bad token, out-of-range offset, too many offsets, empty
    list) is rejected with an Italian error message; the DB is not touched.
- **`/personalizza_orari default`** resets the offsets to `settings.reminder_offsets`
  (same write path as above, using the configured default instead of parsed
  args).
- **No arguments**: read-only, shows the chat's current offsets (or that
  reminders aren't active) plus a usage example. No admin check.
- In groups/supergroups, the with-arguments and `default` forms are
  **admin-only**, reusing the same check as `/promemoria_on`/`/promemoria_off`
  (ADR 0012: anonymous admin or `administrator`/`creator` status). The no-args
  form is open to everyone, like `/promemoria`.

Changing offsets never touches `sent_reminders`: dedup stays keyed on
`(chat_id, round, offset_seconds)`, so a mid-matchday offset change can only
add or drop future reminders for that chat, never duplicate or resend one
already delivered.

## Alternatives considered

- **Arguments on `/promemoria_on`** (`/promemoria_on 24h 1h`): one fewer
  command, but breaks the ADR 0012 guarantee that `/promemoria_on` never
  overwrites offsets, and makes the "no args vs. args" behavior of a single
  command harder to document.
- **Absolute times instead of offsets** (e.g. "remind me at 20:00"): the data
  model and planner (`reminders/planner.py`) already work in
  offset-before-deadline terms; absolute times would need a conversion layer
  and behave oddly across matchdays with different kickoff times.
- **No validation limits**: simpler, but a 0-second or multi-month offset is
  either meaningless or would silently miss the calendar refresh window
  (matchdays far in the future have placeholder kickoff times, see
  `docs/HANDOFF.md`).

## Consequences

- The reminder engine, planner, and dedup logic are unchanged; the command is
  an `UPDATE`/`INSERT` on `subscriptions` plus the existing
  `reschedule_reminders`.
- The BotFather command list must be updated manually (both bots) with
  `personalizza_orari`, same scope as `promemoria_on`/`promemoria_off`
  (*Direct Messages* + *Group Administrators*).
