# Architecture

FantaFormazioni Bot is a single-process Telegram bot (long polling) that reminds a Telegram channel to set the Fantacalcio lineup before each Serie A matchday deadline.

Design decisions and their rationale live in [docs/adr/](adr/). This file describes how the pieces fit together.

## Components

```
src/fantaformazionibot/
  __main__.py            entrypoint: python -m fantaformazionibot
  app.py                 builds the PTB Application, wires handlers and jobs
  config.py              Settings (pydantic-settings): env parsing/validation, duration parsing
  models.py              Matchday (round, kickoff UTC), Subscription, PlannedReminder
  calendar/
    base.py              CalendarProvider protocol + factory (CALENDAR_PROVIDER)
    fixturedownload.py   httpx download of the UTC CSV + pure parse function
  storage/
    repository.py        all SQL (sqlite3, WAL); schema created at startup
  reminders/
    planner.py           pure logic: deadline = kickoff − margin, reminder times, filtering
    jobs.py              PTB jobs: daily calendar refresh, reminder send, (re)scheduling
  telegram/
    commands.py          /start /help /prossima_scadenza /promemoria_on /promemoria_off
                         /promemoria + unknown-command fallback
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

`refresh_calendar_job` → provider fetch → upsert matchdays → drop all scheduled reminder jobs (name prefix `reminder:`) → recompute plan → schedule again. Kickoff changes during the season are picked up here.

### Subscribing a chat

`/promemoria_on` inserts a `subscriptions` row for the current chat (`origin='user'`,
default offsets from `REMINDER_OFFSETS`) and triggers `reschedule_reminders`;
`/promemoria_off` deletes it (only `origin='user'` rows) and reschedules;
`/promemoria` shows the current state. In groups, on/off are admin-only (ADR 0012).

### Sending a reminder

Each reminder job carries `(chat_id, round, offset_seconds)`. On fire it:

1. re-checks `sent_reminders` (dedupe across restarts/reschedules);
2. sends the reminder message with the deadline time and remaining duration;
3. records the reminder in `sent_reminders`.

Reminders whose time is already in the past at scheduling time are skipped, never sent late.

## Database schema

```sql
matchdays      (round INTEGER PRIMARY KEY, kickoff_utc TEXT NOT NULL)          -- real kickoff, ISO 8601 UTC
subscriptions  (chat_id INTEGER PRIMARY KEY, chat_type TEXT NOT NULL,
                reminder_offsets TEXT NOT NULL,                                -- JSON array of seconds
                origin TEXT NOT NULL DEFAULT 'env')                            -- 'env' (config-seeded) | 'user'
sent_reminders (chat_id INTEGER, round INTEGER, offset_seconds INTEGER,
                UNIQUE(chat_id, round, offset_seconds))
```

The DB is fully regenerable from the feed except `sent_reminders` (worst case after deletion: one duplicate reminder).

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
| `CALENDAR_PROVIDER` | no | `fixturedownload` | Calendar source (ADR 0007) |
| `CALENDAR_URL` | no | fixturedownload UTC CSV | Feed URL, supports `{season_year}` |
| `CALENDAR_REFRESH_TIME` | no | `02:00` | Daily refresh time (Europe/Rome, `HH:MM`) |
| `DATABASE_PATH` | no | `fantaformazionibot.db` | SQLite file path |
| `DEADLINE_MARGIN` | no | `5m` | Deadline = kickoff − margin (ADR 0006) |
| `REMINDER_OFFSETS` | no | `24h,1h,5m` | Reminder times before the deadline |
| `ALLOWED_CHAT_IDS` | no | empty (open) | If non-empty, commands are answered only in these chats (dev bot whitelist) |

Durations accept `Ns`, `Nm`, `Nh` (e.g. `24h`, `90m`, `30s`).
