# Architecture

Fanta Formazioni Bot is a single-process Telegram bot (long polling) that reminds a Telegram channel to set the Fantacalcio lineup before each Serie A matchday deadline.

Design decisions and their rationale live in [docs/adr/](adr/). This file describes how the pieces fit together.

## Components

```
src/fantaformazionibot/
  __main__.py            entrypoint: python -m fantaformazionibot
  app.py                 builds the PTB Application, wires handlers and jobs
  config.py              Settings (pydantic-settings): env parsing/validation, duration parsing
  models.py              Matchday (round, kickoff UTC), Subscription, PlannedReminder
  calendar/
    base.py              CalendarProvider protocol + factory (CALENDAR_PROVIDER) + season_year
    fixturedownload.py   httpx download of the UTC CSV + pure parse function
    football_data_org.py httpx call to the football-data.org API + pure parse function (ADR 0014)
    mock.py              dev-only: fabricates a near-future round-1 kickoff for testing (ADR 0016)
  storage/
    repository.py        all SQL (sqlite3, WAL); schema created at startup
  reminders/
    planner.py           pure logic: deadline = kickoff − margin, reminder times, filtering
    jobs.py              PTB jobs: daily calendar refresh, reminder send, (re)scheduling
  telegram/
    commands.py          /start /help /prossima_scadenza /promemoria_on /promemoria_off
                         /promemoria /personalizza_orari /ho_schierato /iscrizioni
                         + unknown-command fallback; subscribe/unsubscribe/set_offsets/
                         confirm_lineup/undo_lineup_confirmation/confirm_group_lineup/
                         undo_group_lineup_confirmation are shared with callbacks.py
    keyboards.py         inline keyboard builders + callback_data codec (pure, ADR 0015)
    callbacks.py         CallbackQueryHandler entry points + the "Personalizzati"
                         ConversationHandler (free-form offset input, ADR 0015)
    errors.py            error handler → DEBUG_CHAT_ID
    messages.py          all user-facing Italian texts (HTML parse mode)
  format.py              Italian date/duration formatting (static month names, zoneinfo)
```

## Flows

### Startup

1. `Settings` loads and validates env (fail fast on missing `TOKEN`, `CHANNEL_CHAT_ID`, `DEBUG_CHAT_ID`).
2. Repository opens the SQLite file (WAL) and creates tables if missing.
3. The channel subscription is upserted from `CHANNEL_CHAT_ID` + `REMINDER_OFFSETS` (ADR 0008).
4. The calendar provider fetches the season's matchdays; kickoffs are upserted into `matchdays`.
5. The reminder plan is computed and every future reminder is scheduled as a `run_once` job (ADR 0005).
6. The daily refresh job is scheduled at `CALENDAR_REFRESH_TIME` (default 02:00 Europe/Rome).
7. Long polling starts.

### Daily calendar refresh

`refresh_calendar_job` → provider fetch → upsert matchdays → staleness check → drop all scheduled reminder jobs (name prefix `reminder:`) → recompute plan → schedule again. Kickoff changes during the season are picked up here.

The staleness check (ADR 0014) looks at the next upcoming matchday: if its deadline is under 3 days away and its kickoff is still an all-zero UTC placeholder, it sends a warning to `DEBUG_CHAT_ID` suggesting a review of `CALENDAR_PROVIDER`. It re-fires on every refresh while the condition holds; switching providers is still a manual env change + redeploy.

### Subscribing a chat

`/promemoria_on` inserts a `subscriptions` row for the current chat (`origin='user'`,
default offsets from `REMINDER_OFFSETS`) and triggers `reschedule_reminders`;
`/promemoria_off` deletes it (only `origin='user'` rows) and reschedules;
`/promemoria` shows the current state. In groups, on/off are admin-only (ADR 0012).
`/personalizza_orari` updates `reminder_offsets` on the chat's row (auto-subscribing
if none exists) or resets it to the configured default with `default`; same
admin-only rule in groups (ADR 0013).

### Inline keyboards (ADR 0015)

`/start`, `/promemoria` and `/personalizza_orari` (no args) attach inline
keyboards on top of the same subscribe/unsubscribe/set-offsets logic
(`telegram/commands.py`'s `subscribe`/`unsubscribe`/`set_offsets`, reused by
`telegram/callbacks.py`). The offsets grid is a multi-select over 8 presets
(2g/24h/12h/3h/1h/30m/10m/5m); which ones are checked travels statelessly in
`callback_data` as a bitmask (`telegram/keyboards.py`), so it survives a bot
restart. Every button press edits the pressed message in place. The
**Personalizzati** button starts a `ConversationHandler` that prompts with
`ForceReply` for a free-form value (e.g. `2g,12h,10m`, parsed with the same
`parse_offsets_args` as the text command) and exits via **⬅️ Indietro**,
`/annulla`, or a 5-minute timeout — all three restore the original grid.
Admin enforcement (ADR 0012) is re-checked per callback, since any group
member can press a button.

### Sending a reminder

Each reminder job carries `(chat_id, round, offset_seconds)`. On fire it:

1. re-checks `sent_reminders` (dedupe across restarts/reschedules);
2. re-checks `lineup_confirmations` (skip if the chat already confirmed this round's lineup, ADR 0021);
3. sends the reminder message with the deadline time and remaining duration —
   private chats also get a "✅ Ho schierato" button;
4. records the reminder in `sent_reminders` (dedupe) and appends a `reminder_send` row to `bot_events` — `sent`, or `failed` with the error kind, which is where the delivery rate comes from (ADR 0029).

Reminders whose time is already in the past at scheduling time are skipped, never sent late.

If Telegram refuses the delivery because the chat is gone for good — the bot was
blocked, kicked, or removed — the subscription is pruned and that chat's pending
reminder jobs are cancelled (ADR 0023). The env-owned channel row is the
exception: it is kept and reported to `DEBUG_CHAT_ID`, since `_post_init`
re-seeds it anyway and only a human can restore the bot's access. A transient
refusal (a closed forum topic) loses that one reminder and changes nothing else.

### Confirming a lineup — "Ho schierato" (ADR 0021, ADR 0027)

In **private chats**, `/ho_schierato` and the "✅ Ho schierato" button on
reminder messages both call `commands.confirm_lineup`, which inserts a
`lineup_confirmations` row for `(chat_id, round)` and calls
`reschedule_reminders` — the same full drop-and-rebuild used by
subscribe/unsubscribe/set_offsets, which now also skips any round already in
`lineup_confirmations`. A "↩️ Annulla conferma" button (`commands.undo_lineup_confirmation`)
deletes the row and reschedules again, resuming the round's remaining
reminders. Confirmations are per-round, so round N+1 is unaffected and needs
no explicit reset.

In **groups** (ADR 0027) a subscription is shared by several distinct managers, so
confirmations are tracked per `(chat_id, round, user_id)` in
`group_lineup_confirmations` against a roster in `group_participants`. The Bot API
cannot enumerate non-admin members, so the roster is built lazily: `/iscrizioni` posts
the "🙋 Sono un manager" self-registration button (anyone may press), an admin closes
enrollment with "🔒 Chiudi iscrizioni", and confirming also enrols the presser while
enrollment is open. `commands.confirm_group_lineup` writes the per-user row and then
`_sync_group_silencing` keeps the per-chat `lineup_confirmations` flag in sync — set
when every roster member has confirmed, cleared when one undoes. That is what lets
`reminders/jobs.py` keep a single skip condition (`is_lineup_confirmed(chat_id, round)`)
for both private and group chats. The reminder keyboard carries the counter in the
button label ("✅ Ho schierato (3/5)"), re-read from the DB after each write.
"🔓 Riapri iscrizioni" (admin) resets roster, confirmations and silencing flags for the
chat. Accepted limit: whoever never registers never enters the roster, so "everyone
confirmed" is an approximation — see ADR 0027.

The channel keeps no button at all (ADR 0021): many subscribers, no meaningful roster.

## Database schema

```sql
matchdays            (round INTEGER PRIMARY KEY, kickoff_utc TEXT NOT NULL)          -- real kickoff, ISO 8601 UTC
subscriptions         (chat_id INTEGER PRIMARY KEY, chat_type TEXT NOT NULL,
                       reminder_offsets TEXT NOT NULL,                               -- JSON array of seconds
                       origin TEXT NOT NULL DEFAULT 'env',                           -- 'env' (config-seeded) | 'user'
                       message_thread_id INTEGER)                                    -- forum topic to deliver to, NULL = none (ADR 0025)
sent_reminders        (chat_id INTEGER, round INTEGER, offset_seconds INTEGER,
                       UNIQUE(chat_id, round, offset_seconds))
lineup_confirmations  (chat_id INTEGER, round INTEGER, UNIQUE(chat_id, round))       -- ADR 0021; for groups it is the derived silencing flag (ADR 0027)
group_participants    (chat_id INTEGER, user_id INTEGER, joined_at TEXT NOT NULL,
                       UNIQUE(chat_id, user_id))                                     -- lazy group roster (ADR 0027)
group_rosters         (chat_id INTEGER PRIMARY KEY, closed_at TEXT)                  -- NULL = enrollment open (ADR 0027)
group_lineup_confirmations (chat_id INTEGER, round INTEGER, user_id INTEGER,
                       UNIQUE(chat_id, round, user_id))                              -- ADR 0027
subscription_events   (id INTEGER PK, chat_id, chat_type, origin, event, occurred_at) -- ADR 0024
bot_events            (id INTEGER PK, occurred_at TEXT NOT NULL,                     -- ISO 8601 UTC
                       action TEXT NOT NULL, outcome TEXT NOT NULL,
                       chat_id INTEGER,                                              -- NULL for process events
                       chat_type TEXT, user_id INTEGER, round INTEGER,
                       detail TEXT)                                                  -- JSON of the remaining fields (ADR 0029)
```

`subscription_events` is the append-only lifecycle log read by *osservatorio-hq* (ADR 0024): `subscribed` on a real insert, `unsubscribed` on `/promemoria_off` (still a user, just not active), `dead_chat` on the pruning of ADR 0023 (unreachable). The bot never reads it; each row is written in the same transaction as the `subscriptions` change it describes.

`bot_events` is the append-only "what happened, and when" log read by *osservatorio-hq* (ADR 0029). One row = one fact that actually happened, with its instant and its outcome — never an intention, never a poll, never a read. It is written from the same single emission point as the log lines of ADR 0028 (`telegram/events.py`), so the two sinks cannot disagree; `chat_type`, `user_id` and `round` are promoted to columns because they are the axes the dashboard aggregates on, everything else rides in `detail` as JSON. Actions in use: `subscribe`, `unsubscribe`, `set_offsets`, `lineup_confirm`, `lineup_undo`, `group_lineup_confirm`, `group_lineup_undo`, `roster_join`, `roster_close`, `roster_reset`, `topic_rebind`, `start`, `bot_added`, `permission_check`, `reminder_send`, `calendar_refresh`, `calendar_stale`, `startup`. **Adding an action is safe; renaming or repurposing one is breaking for the dashboard.** Read-only commands are deliberately not recorded (ADR 0028 §1). The bot never reads the table.

In forum-mode supergroups, running `/promemoria_on` or `/personalizza_orari` (command or button) inside a topic binds that chat's reminders to that topic (`message_thread_id`); running it again from a different topic moves the binding (ADR 0025). Outside forums, and in "General", `message_thread_id` stays `NULL` and delivery is unchanged. Since ADR 0031 the binding is also reachable from the keyboard: in a forum, `/promemoria` renders a second button — "Manda in questo topic" when the current topic differs from the bound one, "Riporta in chat principale" when it is already bound — behind the same admin gate as the on/off toggle, and states the current destination in its text. Neither path reschedules anything: `send_reminder_job` re-reads the subscription at send time.

Onboarding and sharing (ADR 0032): `/start` accepts a deep-link payload (`t.me/<bot>?start=<slug>`) purely as attribution — it records one `start` event with `source=<slug>` and changes no state; the payload is attacker-controllable, so anything outside `[A-Za-z0-9_-]{1,32}` is recorded as `invalid` and never echoed into the log line. In private chats `/start`'s keyboard carries a second, url-only button that opens Telegram's group picker (`?startgroup=true`). `telegram/chatmember.py` answers `my_chat_member`: when the bot actually enters a group or supergroup it sends one welcome with the `/promemoria` keyboard and creates **no** subscription — activation stays an admin's explicit act. That handler re-checks `ALLOWED_CHAT_IDS` itself, since `ChatMemberHandler` takes no filters.

Inline mode (ADR 0033): `@bot` in any chat answers with two cards — the next deadline first (what pressing enter sends), the invite second. It is a pure read: no subscription, no scheduling, and the query text is deliberately ignored. `telegram/inline.py` gates on `allowed_user_ids`, answers with `cache_time=30` so the countdown cannot go stale, and records one `inline_share` row per *chosen* result (never per typed query — that would be traffic, ADR 0028 §1). That last update only arrives if BotFather's `/setinlinefeedback` is enabled.

`matchdays` fully regenerates from the calendar feed. `sent_reminders`, `lineup_confirmations` and the three `group_*` tables are disposable (worst case after deletion: a duplicate reminder, a round's reminders un-silencing, or a group roster to rebuild). `subscriptions` is **not** regenerable: it holds every user/group's `/promemoria_on` state and (since ADR 0013) custom `reminder_offsets` — back it up before anything destructive. Neither are `subscription_events` and `bot_events`: they are history, so nothing can rebuild them and no backfill is allowed to invent one (ADR 0022).

## Datetime policy

- Feed parsed as UTC (the fixturedownload URL uses the `-UTC` variant).
- Stored as ISO 8601 UTC strings.
- Converted to `Europe/Rome` (stdlib `zoneinfo`) only in `format.py` for display.
- No naive datetimes anywhere; no `locale.setlocale` (Italian month names are a static map).

## Message formatting

Telegram messages use **HTML parse mode** (not MarkdownV2): static texts need no escaping and dynamic values are escaped with `html.escape`. All texts live in `telegram/messages.py`.

## Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `TOKEN` | yes | — | Bot token from BotFather |
| `CHANNEL_CHAT_ID` | yes | — | Chat id of the reminder channel |
| `DEBUG_CHAT_ID` | yes | — | Chat id receiving error reports |
| `CALENDAR_PROVIDER` | no | `fixturedownload` | Calendar source: `fixturedownload`, `football-data-org` or `mock` (ADR 0007/0014/0016) |
| `CALENDAR_URL` | no | fixturedownload UTC CSV | Feed URL, supports `{season_year}` (fixturedownload only) |
| `FOOTBALL_DATA_API_KEY` | only if `CALENDAR_PROVIDER=football-data-org` | — | API key for football-data.org (ADR 0014) |
| `MOCK_KICKOFF_OFFSET` | no | `10m` | Fake round-1 kickoff, relative to now; only used if `CALENDAR_PROVIDER=mock` — **dev only** (ADR 0016) |
| `CALENDAR_REFRESH_TIME` | no | `02:00` | Daily refresh time (Europe/Rome, `HH:MM`) |
| `DATABASE_PATH` | no | `fantaformazionibot.db` | SQLite file path |
| `DEADLINE_MARGIN` | no | `5m` | Deadline = kickoff − margin (ADR 0006) |
| `REMINDER_OFFSETS` | no | `24h,1h,5m` | Reminder times before the deadline |
| `URGENT_REMINDER_THRESHOLD` | no | `10m` | Reminders at or under this offset use the fixed "last-call" template instead of the rotating pool (ADR 0018 §9) |
| `ALLOWED_CHAT_IDS` | no | empty (open) | If non-empty, commands are answered only in these chats (dev bot whitelist) |
| `ALLOWED_USER_IDS` | no | empty (open) | If non-empty, inline queries are answered only for these users. Inline updates carry no chat, so `ALLOWED_CHAT_IDS` cannot gate them (ADR 0033) |

Durations accept `Nm`, `Nh`, `Ng` (e.g. `24h`, `90m`, `2g`); `Ns` is still parsed but no longer shown in user-facing text (ADR 0015).
