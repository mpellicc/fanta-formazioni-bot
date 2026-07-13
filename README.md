# Fanta Formazioni Bot

A Telegram bot that reminds you to set your **Fantacalcio** lineup before each Serie A matchday deadline.

Reminders are posted to the [@fantaformazionireminders](https://t.me/fantaformazionireminders) channel by default, and can also be subscribed to directly in any private chat or group. Reminders fire at configurable times before the deadline (by default 24 hours, 1 hour, and 5 minutes, customizable per chat). The deadline is the kickoff of the round's first match minus a configurable safety margin (5 minutes by default).

## Commands

- `/start` — introduction to the bot
- `/prossima_scadenza` — next matchday's deadline and remaining time
- `/promemoria_on` — subscribe to reminders in the current chat
- `/promemoria_off` — unsubscribe from reminders in the current chat
- `/promemoria` — show whether reminders are active and with which offsets
- `/personalizza_orari` — set custom reminder offsets for the current chat (or `/personalizza_orari default` to reset)
- `/help` — list of commands

In groups, `/promemoria_on`, `/promemoria_off`, and `/personalizza_orari` are restricted to group administrators.

`/start`, `/promemoria`, and `/personalizza_orari` also come with inline buttons: a toggle to turn reminders on/off, and a grid of common offset presets (plus a "Personalizzati" button for free-form values) so reminders can be managed by tapping instead of typing.

## How it works

- The Serie A calendar is fetched from [fixturedownload.com](https://fixturedownload.com) (CSV, UTC) at startup and refreshed daily; the source is pluggable via `CALENDAR_PROVIDER`.
- Each reminder is scheduled as an exact-time job; sent reminders are tracked in SQLite so restarts never cause duplicates.
- See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design and [docs/adr/](docs/adr/) for the architectural decision records.

## Development

Requires [uv](https://docs.astral.sh/uv/) (Python 3.13 is provisioned automatically).

```bash
git clone https://github.com/mpellicc/fanta-formazioni-bot.git
cd fanta-formazioni-bot
uv sync

cp .env.example .env   # fill in TOKEN, CHANNEL_CHAT_ID, DEBUG_CHAT_ID

uv run python -m fantaformazionibot
```

Checks:

```bash
uv run ruff check && uv run ruff format --check
uv run mypy src
uv run pytest
```

## Running with Docker

```bash
cp .env.example .env   # fill in the required values
docker compose up -d --build
```

The SQLite database lives on the `bot-data` volume. Production deployment (Oracle Cloud Always Free + GitHub Actions) is documented in [docs/DEPLOY.md](docs/DEPLOY.md).

## Configuration

All configuration is via environment variables (or `.env`); see [.env.example](.env.example) for the full list and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#environment-variables) for details. Required: `TOKEN` (from [@BotFather](https://core.telegram.org/bots#botfather)), `CHANNEL_CHAT_ID`, `DEBUG_CHAT_ID`.

## Contributing

Contributions are welcome! Please open an issue or a pull request. Before proposing architectural changes, check the relevant ADR in [docs/adr/](docs/adr/).

## License

GNU GPLv3 — see [COPYING](COPYING).

---

**Disclaimer:** This project is not affiliated with or endorsed by Telegram or any Fantacalcio league or platform. It is a personal project created for educational and entertainment purposes.
