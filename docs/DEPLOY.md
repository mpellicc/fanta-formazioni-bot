# Deployment

Runtime host: an **Oracle Cloud Always Free** Ampere (ARM) VM running the bot as a Docker container (ADR 0009). CI/CD is GitHub Actions → GHCR → SSH.

## One-time VM setup (manual)

1. **Create the VM** in the Oracle Cloud console:
   - Shape: `VM.Standard.A1.Flex` (Always Free eligible), 1 OCPU / 6 GB is more than enough.
   - Image: Ubuntu LTS (aarch64).
   - Add your SSH public key.
2. **Install Docker** (with the compose plugin):

   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER  # re-login afterwards
   ```

3. **Prepare the app directory**:

   ```bash
   mkdir -p ~/fantaformazionibot && cd ~/fantaformazionibot
   # copy compose.yaml from the repo, then create the env file:
   cp env.example .env   # fill in TOKEN, CHANNEL_CHAT_ID, DEBUG_CHAT_ID
   ```

   The compose file uses the prebuilt GHCR image; the SQLite DB lives on the named volume `bot-data`.

4. **First start**:

   ```bash
   docker compose pull && docker compose up -d
   docker compose logs -f   # check startup: calendar fetched, reminders scheduled
   ```

## CI/CD

- **`.github/workflows/ci.yml`** — on every push and PR: `uv sync`, `ruff check`, `ruff format --check`, `mypy src`, `pytest`.
- **`.github/workflows/deploy.yml`** — on push to `main` (after CI passes):
  1. Build the image for `linux/arm64` with buildx and push to `ghcr.io/<owner>/fanta-formazioni-bot:latest` (plus the commit SHA tag).
  2. SSH into the VM and run `docker compose pull && docker compose up -d`.

### Required repository secrets

| Secret | Purpose |
|---|---|
| `SSH_HOST` | VM public IP |
| `SSH_USER` | VM user (e.g. `ubuntu`) |
| `SSH_KEY` | Private key matching the VM's authorized key |

`GITHUB_TOKEN` (automatic) is used to push to GHCR. If the GHCR package is private, run `docker login ghcr.io` once on the VM with a read-only PAT.

## Operations

- **Logs**: `docker compose logs -f`
- **Restart**: `docker compose restart`
- **Manual deploy**: re-run the deploy workflow, or on the VM `docker compose pull && docker compose up -d`
- **DB backup**: `docker run --rm -v fantaformazionibot_bot-data:/data -v $PWD:/backup alpine cp /data/fantaformazionibot.db /backup/` — losing it only loses sent-reminder markers.
- **Errors at runtime** are sent by the bot itself to `DEBUG_CHAT_ID`.
