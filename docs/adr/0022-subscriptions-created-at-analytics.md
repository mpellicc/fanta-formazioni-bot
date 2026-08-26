# ADR 0022: `subscriptions.created_at` and an external read-only analytics consumer

- Status: accepted
- Date: 2026-08-26

## Context

We want to know how many chats are subscribed, broken down by `chat_type` and
`origin`, and how that grows over time. `subscriptions` (ADR 0008) is
point-in-time: a row tells you a chat is subscribed now, not since when, so
growth cannot be reconstructed from it.

The consumer is a local dashboard (separate repo, out of scope here) that will
connect to the VM over SSH and query the SQLite file directly, read-only. The
bot itself gains no new behavior: no HTTP endpoint, no new dependency, nothing
that runs at request time.

The real decision here is not "add a column" — it's that the bot's SQLite
schema stops being purely internal. `subscriptions` becomes a table another
system reads directly, which we're accepting as a real (if narrow) coupling.

## Decision

Add `created_at TEXT` (ISO 8601 UTC, tz-aware) to `subscriptions`, migrated
for existing databases with the same `PRAGMA table_info` + `ALTER TABLE`
guard already used for the `origin` column (ADR 0008 amendment).

- `upsert_subscription` sets `created_at` on `INSERT` only; the
  `ON CONFLICT ... DO UPDATE` clause does not touch it, so re-seeding the
  env-owned channel row (or a repeated `/promemoria_on`) never resets it.
- Existing rows get `NULL` on migration, deliberately — not backfilled with
  today's date or the migration date. `NULL` means "subscribed before we
  started tracking"; inventing a value would fabricate growth-chart history
  that never happened.
- `Subscription` (`models.py`) and the `SELECT` read paths do **not** gain a
  `created_at` field. The bot has no runtime use for it — the dashboard reads
  the column directly via SQL. Adding it to the model and every query would
  be complexity with no in-process consumer.
- Access from the dashboard is read-only, over SSH into the VM, against the
  existing SQLite file. The bot exposes no new network surface and its
  runtime behavior is unchanged.

## Alternatives considered

- **Backfill existing rows with the migration timestamp**: makes every
  pre-migration subscriber look like they joined on the same day, producing a
  misleading spike in any growth chart. Rejected.
- **`DEFAULT CURRENT_TIMESTAMP` on the column**: SQLite's `CURRENT_TIMESTAMP`
  is naive UTC text, not the tz-aware ISO 8601 the rest of the codebase
  standardizes on; it would also hide the write behind SQLite rather than
  making it an explicit Python value. Rejected.
- **Add `created_at` to `Subscription` and all `SELECT`s**: keeps the schema
  and the in-process model in sync, but nothing in the bot reads the field —
  it would be plumbing for a consumer that talks SQL directly. Rejected
  unless a concrete in-process need for it appears.
- **A dedicated events/history table instead of a column**: would support
  richer analytics (e.g. re-subscribe history) but is unwarranted for a
  single "when did this row first appear" question; `delete_user_subscription`
  already removes the row on unsubscribe, so a resubscribe naturally gets a
  fresh `created_at` via a new `INSERT`.

## Consequences

- `subscriptions`'s schema is no longer freely refactorable without
  considering the external dashboard: renaming or dropping `chat_id`,
  `chat_type`, `origin`, or `created_at` — or changing their meaning — is now
  a breaking change for a consumer outside this repo, even though nothing
  in-repo enforces that.
- Growth metrics undercount by construction for any chat subscribed before
  this migration shipped (their `created_at` is `NULL`); the dashboard must
  treat `NULL` as "unknown join date," not as zero or an error.
- No change to the bot's process model, dependencies, or network exposure.
