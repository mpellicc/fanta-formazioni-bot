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
                         /promemoria /personalizza_orari /ho_schierato + unknown-command
                         fallback; subscribe/unsubscribe/set_offsets/confirm_lineup/
                         undo_lineup_confirmation are shared with callbacks.py
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
4. records the reminder in `sent_reminders`.

Reminders whose time is already in the past at scheduling time are skipped, never sent late.

If Telegram refuses the delivery because the chat is gone for good — the bot was
blocked, kicked, or removed — the subscription is pruned and that chat's pending
reminder jobs are cancelled (ADR 0023). The env-owned channel row is the
exception: it is kept and reported to `DEBUG_CHAT_ID`, since `_post_init`
re-seeds it anyway and only a human can restore the bot's access. A transient
refusal (a closed forum topic) loses that one reminder and changes nothing else.

### Confirming a lineup — "Ho schierato" (ADR 0021)

Private chats only (a group/channel subscription is shared by several
distinct managers — see ADR 0021 for why that rules out a correct group
version for now). `/ho_schierato` and the "✅ Ho schierato" button on
reminder messages both call `commands.confirm_lineup`, which inserts a
`lineup_confirmations` row for `(chat_id, round)` and calls
`reschedule_reminders` — the same full drop-and-rebuild used by
subscribe/unsubscribe/set_offsets, which now also skips any round already in
`lineup_confirmations`. A "↩️ Annulla conferma" button (`commands.undo_lineup_confirmation`)
deletes the row and reschedules again, resuming the round's remaining
reminders. Confirmations are per-round, so round N+1 is unaffected and needs
no explicit reset.

## Database schema

```sql
matchdays            (round INTEGER PRIMARY KEY, kickoff_utc TEXT NOT NULL)          -- real kickoff, ISO 8601 UTC
subscriptions         (chat_id INTEGER PRIMARY KEY, chat_type TEXT NOT NULL,
                       reminder_offsets TEXT NOT NULL,                               -- JSON array of seconds
                       origin TEXT NOT NULL DEFAULT 'env')                           -- 'env' (config-seeded) | 'user'
sent_reminders        (chat_id INTEGER, round INTEGER, offset_seconds INTEGER,
                       UNIQUE(chat_id, round, offset_seconds))
lineup_confirmations  (chat_id INTEGER, round INTEGER, UNIQUE(chat_id, round))       -- ADR 0021
```

`matchdays` fully regenerates from the calendar feed. `sent_reminders` and `lineup_confirmations` are disposable (worst case after deletion: a duplicate reminder, or a round's reminders un-silencing). `subscriptions` is **not** regenerable: it holds every user/group's `/promemoria_on` state and (since ADR 0013) custom `reminder_offsets` — back it up before anything destructive.

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

Durations accept `Nm`, `Nh`, `Ng` (e.g. `24h`, `90m`, `2g`); `Ns` is still parsed but no longer shown in user-facing text (ADR 0015).
