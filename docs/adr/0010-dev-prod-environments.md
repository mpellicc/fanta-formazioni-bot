# ADR 0010: Dev/prod environments via GitHub Environments and two bots

- Status: accepted, **amended by ADR 0017** (2026-07-08)
- Date: 2026-07-06

## Context

With `main` as the production branch and `dev` as the integration branch, changes need a place to be tested against Telegram before reaching the production channel. Two constraints shape the solution:

- Telegram long polling forbids two processes sharing one bot token (`getUpdates` conflict), so a dev deployment running alongside prod requires a **separate bot**.
- Editing the `.env` on the VM over SSH for every config change (token rotation, chat id change) is error-prone and manual.

## Decision

- **Two deployed instances on the same VM**, one per trigger:
  - push to `main` → environment `development` → `~/fantaformazionibot-dev`, image `:dev`, dev bot (BotFather) posting to the debug chat
  - push of a tag `v*` → environment `production` → `~/fantaformazionibot`, image `:latest` (+ the immutable `:X.Y.Z`), production bot/channel
- **GitHub Environments** hold the per-environment configuration: `BOT_TOKEN` as an environment secret, `CHANNEL_CHAT_ID` and `DEBUG_CHAT_ID` as environment variables. `SSH_HOST`/`SSH_USER`/`SSH_KEY` stay repository-level (the VM is shared).
- **The pipeline owns the VM state**: on every deploy it copies `compose.yaml` and regenerates `.env` from the environment's secrets/vars. Changing configuration = edit the value on GitHub → re-run Deploy. Manual edits on the VM get overwritten by design.

> **Amendment (ADR 0017, 2026-07-08):** the branch model changed from
> `dev`/`main` mirrors to trunk (`main`) + tag releases. The two GitHub
> Environments, their secrets/vars, and the shared-VM/two-bot setup described
> above are unchanged — only the *trigger* moved from "which branch" to "branch
> push vs. tag push" (bullet list above reflects the new mapping). See ADR 0017
> for the full model and migration.

## Alternatives considered

- **Single bot, deploy only from `main`**: no dev testing environment; testing happens only locally.
- **Separate dev VM**: cleaner isolation but burns Always Free capacity for a bot that idles at ~44 MB.
- **Config baked into the image or repo**: would put the token in git history; rejected.

## Consequences

- Both containers share the VM's 1 GB RAM — fine at ~44 MB each, revisit if the bot grows.
- Rotating the prod token: update the `production` environment secret and re-run Deploy.
- The `development` deploy fails (fail-fast validation) until the dev bot token and vars are configured.
