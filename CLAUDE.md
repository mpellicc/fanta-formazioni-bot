# FantaFormazioni Bot — agent guide

Telegram bot (Python 3.13, python-telegram-bot ~22.8, long polling) that reminds a Telegram channel to set the Fantacalcio lineup before each Serie A matchday deadline.

## Commands

```bash
uv sync                      # install deps (creates .venv)
uv run pytest                # tests
uv run ruff check            # lint
uv run ruff format           # format (--check in CI)
uv run mypy src              # strict type checking
uv run python -m fantaformazionibot   # run the bot (needs .env, see .env.example)
docker build .               # container build (multi-arch amd64+arm64 in CI)
```

All four checks (ruff check, ruff format --check, mypy, pytest) must pass before considering work done.

## Where things are

- `src/fantaformazionibot/` — the application code (src layout; run from source, not built as a package — ADR 0017). Modules: `config.py` (pydantic-settings), `calendar/` (provider protocol + fixturedownload/football-data.org/mock implementations), `storage/repository.py` (all SQL, sqlite3+WAL), `reminders/planner.py` (pure scheduling logic) and `reminders/jobs.py` (PTB JobQueue wiring), `telegram/` (command handlers, inline-keyboard builders + callbacks, messages), `format.py` (Italian formatting).
- `tests/` — pytest; pure logic (planner, CSV parsing, config parsing, formatting) is tested without network or Telegram.
- `docs/ARCHITECTURE.md` — components, flows, DB schema, env vars table.
- `docs/adr/` — one ADR per architectural decision. **Read the relevant ADR before changing an architectural choice; add a new ADR when making one.**
- `docs/DEPLOY.md` — Oracle VM setup + CI/CD (GHCR, SSH deploy).
- `docs/HANDOFF.md` — session handoff: current state, infra details, roadmap, working style. Read it at session start; verify volatile facts (open PRs, deployed version) before relying on them.

## Git workflow

- **`main` is the trunk and the default branch** (dev bot deploys from every push to it). Feature branches → PR into `main`, merged with **squash**. See ADR 0017.
- **Releases are git tags** `vX.Y.Z`, not PRs. Tagging a commit on `main` (or on `release-1.0` once cut, see below) and pushing the tag deploys **production** and creates the GitHub Release; no version bump commit, no release PR. The version is not tracked in `pyproject.toml` (removed — ADR 0017).
- **Seasonal maintenance**: once 1.0.0 ships, `release-1.0` is a long-running branch for in-season bugfixes only (patch tags `v1.0.x`). Fix on `main` first, then cherry-pick to `release-1.0` and tag the patch — never fix on `release-1.0` first.
- Do NOT add `Co-Authored-By` trailers to commits or "Generated with" footers to PR bodies.
- Never edit `.env`/`compose.yaml` on the VM: the deploy pipeline overwrites them from GitHub environment secrets/vars (ADR 0010). Config changes = update the GitHub value, re-run Deploy.

## Conventions and invariants

- **Datetimes are always tz-aware.** Stored as ISO 8601 UTC; converted to `Europe/Rome` only in `format.py`. Never use `locale`, `dateutil`, or `pytz` (stdlib `zoneinfo` only).
- **User-facing texts are Italian**, live only in `telegram/messages.py`, and use **HTML parse mode** (escape dynamic values with `html.escape`; never MarkdownV2).
- **All SQL lives in `storage/repository.py`.** No ORM.
- **Reminders are `run_once` jobs at exact times** (never interval polling); dedupe via the `sent_reminders` table. Reschedule = drop jobs with the `reminder:` name prefix and rebuild from DB (see `reminders/jobs.py`).
- **Deadline is derived**: `kickoff − DEADLINE_MARGIN` (config), never stored.
- Keep `reminders/planner.py` pure (no I/O) so it stays trivially testable.
- Config: only via `Settings` in `config.py`, passed through `bot_data["settings"]`; no module-level instances.
- Per-user/group subscriptions and custom offsets (ADR 0012/0013) are done. Further roadmap features (e.g. user-owned channels, see `docs/HANDOFF.md`) should keep extending the `subscriptions` table + add handlers — the reminder engine already iterates subscriptions (ADR 0008) and needs no changes.
