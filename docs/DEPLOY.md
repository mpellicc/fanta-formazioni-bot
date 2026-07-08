# Deployment

Runtime host: an **Oracle Cloud Always Free** VM running the bot as Docker containers (ADR 0009). CI/CD is GitHub Actions → GHCR → SSH. Two instances live on the same VM (ADR 0010, amended by ADR 0017 for the trigger):

| Trigger | GitHub environment | VM directory | Image tag | Bot |
|---|---|---|---|---|
| push to `main` | `development` | `~/fantaformazionibot-dev` | `:dev` | dev bot → debug chat |
| push of a tag `v*` | `production` | `~/fantaformazionibot` | `:latest` (+ immutable `:X.Y.Z`) | production bot → reminder channel |

The pipeline owns the VM state: on every deploy it copies `compose.yaml` and regenerates the `.env` from the environment's secrets/variables. **Do not edit those files on the VM** — changes are overwritten at the next deploy. To change configuration, edit the value on GitHub and re-run Deploy.

## One-time VM setup (manual)

1. **Create the VM** in the Oracle Cloud console: `VM.Standard.A1.Flex` (or `VM.Standard.E2.1.Micro`, both Always Free), Ubuntu LTS image, public IP, your SSH public key.
2. **Install Docker and add swap** (needed on the 1 GB Micro):

   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER  # re-login afterwards
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

3. Generate a dedicated deploy key pair locally, authorize the public half on the VM, and keep the private half for the `SSH_KEY` secret:

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/fantabot_deploy -C "github-actions-deploy" -N ""
   ssh-copy-id -f -i ~/.ssh/fantabot_deploy.pub ubuntu@<VM_IP>
   ```

Everything else (app directories, compose file, env files) is created by the deploy workflow.

## GitHub configuration

**Repository-level secrets** (shared by both environments):

| Secret | Purpose |
|---|---|
| `SSH_HOST` | VM public IP |
| `SSH_USER` | VM user (e.g. `ubuntu`) |
| `SSH_KEY` | Deploy private key |
| `FOOTBALL_DATA_API_KEY` | football-data.org API key (ADR 0014) — one account/key shared by both bots, not per-environment config |

**Per-environment** (Settings → Environments → `production` / `development`):

| Name | Kind | Purpose |
|---|---|---|
| `BOT_TOKEN` | secret | Bot token from BotFather (separate bot per environment — polling forbids sharing) |
| `CHANNEL_CHAT_ID` | variable | Chat receiving reminders (prod: the channel; dev: the debug chat) |
| `DEBUG_CHAT_ID` | variable | Chat receiving error reports |
| `CALENDAR_PROVIDER` | variable | `fixturedownload` (default if unset), `football-data-org` (ADR 0014) or `mock` (ADR 0016, **dev only — never set on `production`**) — settable independently per environment |
| `MOCK_KICKOFF_OFFSET` | variable | Only used if `CALENDAR_PROVIDER=mock`; default `10m` if unset (ADR 0016) |

## Workflows

- **`ci.yml`** — push to `main` and every PR: `ruff check`, `ruff format --check`, `mypy src`, `pytest`. (Once `release-1.0` is cut, it's added here too so cherry-picked fix commits get checked.)
- **`deploy.yml`** — push to `main`, push of a tag `v*`, or manual `workflow_dispatch` (pick the branch or tag to run from): build multi-arch image (amd64+arm64), push to GHCR, then over SSH: copy `compose.yaml`, write `.env` from the environment's config, `docker compose pull && up -d` in the target directory. On a tag push, a `release` job also creates the GitHub Release for that tag.

## Branching and release flow (ADR 0017: trunk + tag releases)

`main` is the trunk and the default branch. Feature branches → PR into `main`, **squash merge** (one commit per feature) — this is the only merge strategy; there are no more release PRs.

**A release is a git tag, not a PR or a workflow run:**

```bash
git checkout main && git pull
git tag v1.1.0
git push origin v1.1.0
```

Pushing the tag builds the image, tags it `:X.Y.Z` + `:latest`, deploys production, and publishes the GitHub Release — all in `deploy.yml`. There is no version bump commit and no separate "Prepare release" step; `pyproject.toml` does not track a version (ADR 0017).

**Seasonal maintenance branch** (`release-1.0`, cut from `main` at the `v1.0.0` tag): during the season, in-season bugfixes are fixed on `main` first (so the trunk never regresses), then cherry-picked onto `release-1.0` and tagged as a patch:

```bash
git checkout release-1.0 && git pull
git cherry-pick <fix-commit-sha>   # the fix, already merged into main
git tag v1.0.3
git push origin release-1.0 v1.0.3
```

Never fix directly on `release-1.0` first — always fix on `main`, then cherry-pick down, to avoid the fix silently missing from the next `main`-based version.

## Operations

- **Logs**: `ssh <vm>` then `docker compose logs -f` in `~/fantaformazionibot` (prod) or `~/fantaformazionibot-dev` (dev)
- **Manual deploy / config reload**: Actions → Deploy → Run workflow (pick `main` for the dev bot, or a `vX.Y.Z` tag for production)
- **Rotate a token**: update the environment secret, re-run Deploy
- **Switch calendar provider** (e.g. after a staleness alert, ADR 0014): set the `CALENDAR_PROVIDER` environment variable to `football-data-org`, re-run Deploy; requires the repo-level `FOOTBALL_DATA_API_KEY` secret to already be set
- **Test a reminder end-to-end on the dev bot** (ADR 0016): on the `development` environment, set `CALENDAR_PROVIDER=mock` (optionally `MOCK_KICKOFF_OFFSET`), re-run Deploy. Then use `/personalizza_orari` on the chat under test to pick short custom offsets so the reminder actually fires within the window. Set `CALENDAR_PROVIDER` back to `fixturedownload` and redeploy when done — the next refresh restores round 1's real kickoff. **Never set `CALENDAR_PROVIDER=mock` on `production`.**
- **DB backup** (prod): `docker run --rm -v fantaformazionibot_bot-data:/data -v $PWD:/backup alpine cp /data/fantaformazionibot.db /backup/` — losing it loses user/group `subscriptions` (everyone who ran `/promemoria_on` would need to redo it) and `sent_reminders` markers; `matchdays` regenerates from the calendar feed
- **Runtime errors** are sent by the bot itself to the environment's `DEBUG_CHAT_ID`

## Migrating to a new VM

The current VM is `VM.Standard.E2.1.Micro` (Always Free); `VM.Standard.A1.Flex` (ARM, 6+ GB, also Always Free) is preferred when Oracle has capacity, which is intermittent — retrying VM creation is the only way to find out. The image is already multi-arch (amd64+arm64, ADR 0009), so no build changes are needed either way.

1. **Create the new VM** in the Oracle Cloud console (Ubuntu LTS, public IP, your personal SSH public key). Oracle's E2.1.Micro and A1.Flex Always Free quotas are separate pools, so the old VM can keep running during the migration (zero-downtime cutover).
2. **Install Docker and add swap** — same commands as [one-time VM setup](#one-time-vm-setup-manual) above.
3. **Authorize the existing deploy key** on the new VM (reuse the same key pair, no new `SSH_KEY` secret needed):
   ```bash
   ssh-copy-id -f -i ~/.ssh/fantabot_deploy.pub ubuntu@<NEW_VM_IP>
   ```
4. **Back up the DB on the old VM**, for each instance you care about preserving (at minimum prod, since it may hold real user/group subscriptions — dev's are just test data). Use the [DB backup](#operations) command with the matching volume name (`fantaformazionibot_bot-data` for prod, `fantaformazionibot-dev_bot-data` for dev). Losing `subscriptions` silently unsubscribes every user/group that ran `/promemoria_on` — this is the one table worth carrying over; `matchdays` regenerates from the calendar feed and losing `sent_reminders` only risks one duplicate reminder.
5. **Update the `SSH_HOST` secret** (repository-level) with the new IP.
6. **Re-run Deploy for both bots** (Actions → Deploy → Run workflow, once from `main` for dev, once from the current production `vX.Y.Z` tag for prod). The pipeline creates the app directories, `compose.yaml` and `.env` from scratch, and the first `docker compose up -d` creates fresh empty volumes on the new VM.
7. **Restore the DB** on the new VM: stop the container (`docker compose stop` in the app directory), copy the backed-up file into the new volume (reverse of the backup command: `docker run --rm -v <volume>:/data -v $PWD:/backup alpine cp /backup/fantaformazionibot.db /data/`), then `docker compose start`.
8. **Verify** both bots on the new VM (`docker compose logs -f` in each app directory, and check `/promemoria` reflects a previously-known subscription) before decommissioning anything.
9. **Terminate the old VM** in the Oracle console once confirmed.
10. **Update the IP** recorded in `docs/HANDOFF.md`.
