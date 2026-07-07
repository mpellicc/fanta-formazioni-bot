# Deployment

Runtime host: an **Oracle Cloud Always Free** VM running the bot as Docker containers (ADR 0009). CI/CD is GitHub Actions → GHCR → SSH. Two instances live on the same VM (ADR 0010):

| Branch | GitHub environment | VM directory | Image tag | Bot |
|---|---|---|---|---|
| `main` | `production` | `~/fantaformazionibot` | `:latest` | production bot → reminder channel |
| `dev` | `development` | `~/fantaformazionibot-dev` | `:dev` | dev bot → debug chat |

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
| `CALENDAR_PROVIDER` | variable | `fixturedownload` (default if unset) or `football-data-org` (ADR 0014) — settable independently per environment |

## Workflows

- **`ci.yml`** — push to `main`/`dev` and every PR: `ruff check`, `ruff format --check`, `mypy src`, `pytest`.
- **`deploy.yml`** — push to `main` or `dev` (or manual `workflow_dispatch`): build multi-arch image (amd64+arm64), push to GHCR with the branch's tag, then over SSH: copy `compose.yaml`, write `.env` from the environment's config, `docker compose pull && up -d` in the branch's directory.

## Branching and release flow

`dev` is the default branch. Feature branches → PR into `dev` (auto-deploys the dev bot) → release PR `dev` → `main` (deploys production).

Releases are versioned via the **Prepare release** workflow (ADR 0011): Actions → Prepare release → run on `dev` choosing patch/minor/major. It bumps `pyproject.toml`, commits `Release vX.Y.Z` to `dev`, and opens the release PR. Merging it deploys production, tags the image (`:X.Y.Z` + `:latest`), creates the git tag `vX.Y.Z`, and publishes the GitHub Release with auto-generated notes.

Merge conventions:

- PRs into `dev`: **squash merge** (one commit per feature).
- Release PRs into `main`: **merge commit** — never squash, or `dev` and `main` histories diverge and later release PRs show phantom conflicts.
- `main` requires one approving review. Release PRs are authored by `github-actions[bot]`, so the repository owner can approve them himself; the release PR shows no CI checks (PRs opened with `GITHUB_TOKEN` don't trigger workflows) — the same code already passed CI on `dev`.

## Operations

- **Logs**: `ssh <vm>` then `docker compose logs -f` in `~/fantaformazionibot` (prod) or `~/fantaformazionibot-dev` (dev)
- **Manual deploy / config reload**: Actions → Deploy → Run workflow (pick the branch)
- **Rotate a token**: update the environment secret, re-run Deploy
- **Switch calendar provider** (e.g. after a staleness alert, ADR 0014): set the `CALENDAR_PROVIDER` environment variable to `football-data-org`, re-run Deploy; requires the repo-level `FOOTBALL_DATA_API_KEY` secret to already be set
- **DB backup** (prod): `docker run --rm -v fantaformazionibot_bot-data:/data -v $PWD:/backup alpine cp /data/fantaformazionibot.db /backup/` — losing it only loses sent-reminder markers
- **Runtime errors** are sent by the bot itself to the environment's `DEBUG_CHAT_ID`
