# Deployment

Runtime host: an **Oracle Cloud Always Free** VM running the bot as Docker containers (ADR 0009). CI/CD is GitHub Actions → GHCR → SSH. Two instances live on the same VM (ADR 0010, amended by ADR 0017 for the trigger):

| Trigger | GitHub environment | VM directory | Image tag | Bot |
|---|---|---|---|---|
| push to `main` | `development` | `~/fantaformazionibot-dev` | `:dev` | dev bot → debug chat |
| push of a tag `v*` | `production` | `~/fantaformazionibot` | `:latest` (+ immutable `:X.Y.Z`) | production bot → reminder channel |

The pipeline owns the VM state: on every deploy it copies `compose.yaml` and regenerates the `.env` from the environment's secrets/variables. **Do not edit those files on the VM** — changes are overwritten at the next deploy. To change configuration, edit the value on GitHub and re-run Deploy.

## One-time VM setup (manual)

1. **Create the VM** in the Oracle Cloud console: `VM.Standard.A1.Flex` (current host: 1 OCPU / 6 GB, Ubuntu 26.04 aarch64) or `VM.Standard.E2.1.Micro`, both Always Free; Ubuntu LTS image, your SSH public key.
2. **Reserve the public IP**: instance → Networking → VNIC → IP administration → edit the private IP → *Reserved public IP*. An ephemeral IP is lost if the instance is ever recreated, which would mean updating `SSH_HOST` and every SSH config. If a direct switch is refused, set *No public IP* first, then *Reserved*.
3. **Install Docker** (and swap, only on the 1 GB Micro — A1 does not need it):

   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER  # re-login afterwards
   # E2.1.Micro only:
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

4. Generate a dedicated deploy key pair locally, authorize the public half on the VM, and keep the private half for the `SSH_KEY` secret:

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

- **`ci.yml`** — push to `main` or any `release-*` branch, and every PR: `ruff check`, `ruff format --check`, `mypy src`, `pytest`. The `release-*` glob means a newly cut maintenance line is covered without editing this file.
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

**Seasonal maintenance branch** (`release-X.Y`, cut from `main` at that minor's tag — currently **`release-1.4`**, cut at `v1.4.0`; `release-1.0` through `release-1.3` are retired): during the season, in-season bugfixes are fixed on `main` first (so the trunk never regresses), then cherry-picked onto the release branch and tagged as a patch:

```bash
git checkout release-1.4 && git pull
git cherry-pick <fix-commit-sha>   # the fix, already merged into main
git tag v1.4.6
git push origin release-1.4 v1.4.6
```

Never fix directly on the release branch first — always fix on `main`, then cherry-pick down, to avoid the fix silently missing from the next `main`-based version.

A **minor** does not need the release branch: tag it on `main` and push, exactly as above. Production is selected by the ref being a tag, not by which branch it points into (ADR 0017 decision 3 + amendment). The release branch exists so you can come back and patch that minor once `main` has moved on — cut it at the tag, not when you first need it.

## Operations

- **Logs**: `ssh <vm>` then `docker compose logs -f` in `~/fantaformazionibot` (prod) or `~/fantaformazionibot-dev` (dev)
- **Manual deploy / config reload**: Actions → Deploy → Run workflow (pick `main` for the dev bot, or a `vX.Y.Z` tag for production)
- **Rotate a token**: update the environment secret, re-run Deploy
- **Switch calendar provider** (e.g. after a staleness alert, ADR 0014): set the `CALENDAR_PROVIDER` environment variable to `football-data-org`, re-run Deploy; requires the repo-level `FOOTBALL_DATA_API_KEY` secret to already be set
- **Test a reminder end-to-end on the dev bot** (ADR 0016): on the `development` environment, set `CALENDAR_PROVIDER=mock` (optionally `MOCK_KICKOFF_OFFSET`), re-run Deploy. Then use `/personalizza_orari` on the chat under test to pick short custom offsets so the reminder actually fires within the window. Set `CALENDAR_PROVIDER` back to `fixturedownload` and redeploy when done — the next refresh restores round 1's real kickoff. **Never set `CALENDAR_PROVIDER=mock` on `production`.**
- **DB backup** (prod): `docker run --rm -v fantaformazionibot_bot-data:/data -v $PWD:/backup alpine cp /data/fantaformazionibot.db /backup/` — losing it loses user/group `subscriptions` (everyone who ran `/promemoria_on` would need to redo it) and `sent_reminders`/`lineup_confirmations` markers; `matchdays` regenerates from the calendar feed
- **Runtime errors** are sent by the bot itself to the environment's `DEBUG_CHAT_ID`

## Migrating to a new VM

The current VM is `VM.Standard.A1.Flex` (ARM, 1 OCPU / 6 GB, Always Free), migrated from an `E2.1.Micro` in October 2026 after a host failure (see `docs/HANDOFF.md`). The image is multi-arch (amd64+arm64, ADR 0009), so no build changes are needed in either direction. Moving between x86 (E2) and ARM (A1) is **always a new instance**, never a resize: Oracle can't change a shape across architectures, and the boot image differs.

The DB is the only state worth carrying over: losing `subscriptions` silently unsubscribes every user/group that ran `/promemoria_on`. `matchdays` regenerates from the calendar feed; losing `sent_reminders`/`lineup_confirmations` only risks a duplicate or un-silenced reminder. **No bot may start on the new VM before its DB is in place**: an empty prod DB comes up with no subscriptions and no dedupe markers.

1. **Create the new VM** and set it up as in [one-time VM setup](#one-time-vm-setup-manual) (reserved public IP, Docker, swap only on Micro). Oracle's E2.1.Micro and A1.Flex Always Free quotas are separate pools, so a still-running old VM can keep serving during the migration.
2. **Authorize the existing deploy key** on the new VM (same key pair, no new `SSH_KEY` secret):
   ```bash
   ssh-copy-id -f -i ~/.ssh/fantabot_deploy.pub ubuntu@<NEW_VM_IP>
   ```
3. **Get the DB files**, by one of two routes:
   - **Old VM still running**: stop both bots there (`docker compose stop` in each app directory, so the WAL is checkpointed and nothing writes afterwards), then copy each volume's `_data/` directory to the new VM (e.g. `sudo tar -C /var/lib/docker/volumes -czf - fantaformazionibot_bot-data/_data fantaformazionibot-dev_bot-data/_data | ssh <new-vm> 'sudo tar -C /tmp/old -xzf -'`).
   - **Old VM dead** (won't boot, e.g. no host capacity): in the console, Storage → Boot Volumes → the old instance's boot volume → **Create clone** (e.g. `old-boot-clone`), then on the new instance Attached block volumes → **Attach** → the clone, Paravirtualized, Read/Write. On the VM, `lsblk` shows it (typically `sdb`), and its root partition is `sdb1`. Mount it with `sudo mkdir -p /mnt/old && sudo mount /dev/sdb1 /mnt/old`. The volumes are under `/mnt/old/var/lib/docker/volumes/`.
     - ⚠️ **Relabel the clone's root right away**: `sudo e2label /dev/sdb1 old-rootfs`. Ubuntu cloud images mount `/` by `LABEL=cloudimg-rootfs`, and the clone carries the same label, so a reboot while it's attached may boot from the old disk.
4. **Create the volumes with Compose's labels and copy the DBs in, before any deploy**. The labels make the first `docker compose up` adopt the volume instead of creating an empty one. Copy the whole directory, including `-wal`/`-shm`: after a crash, recent writes may live only in the WAL.
   ```bash
   SRC=/mnt/old/var/lib/docker/volumes   # or wherever step 3 put them
   for v in fantaformazionibot fantaformazionibot-dev; do
     docker volume create --label com.docker.compose.project=$v \
                          --label com.docker.compose.volume=bot-data ${v}_bot-data
     sudo cp -a $SRC/${v}_bot-data/_data/. /var/lib/docker/volumes/${v}_bot-data/_data/
     sudo chown 1000:0 /var/lib/docker/volumes/${v}_bot-data/_data   # 1000 = appuser in the image
   done
   ```
   Optionally check a **copy** (not the volume itself, since opening it checkpoints the WAL): `sqlite3 copy.db 'PRAGMA integrity_check; SELECT count(*) FROM subscriptions;'` (the VM has no `sqlite3`: run it in `alpine` with `apk add sqlite`).
5. **Update the `SSH_HOST` secret** (repository-level) with the new IP.
6. **Deploy both bots** (Actions → Deploy → Run workflow, once from `main` for dev, once from the current production `vX.Y.Z` tag for prod: check `git tag --sort=-v:refname | head -1`). The pipeline creates the app directories, `compose.yaml` and `.env`. Then `docker volume ls` must still show exactly the two `*_bot-data` volumes.
7. **Verify** both bots (`docker compose ps` and `docker compose logs --tail 50` in each app directory: "Scheduled N reminders" with N in line with the subscriptions), and check that `/promemoria` from a previously subscribed chat shows the subscription.
8. **Terminate the old VM** in the console once confirmed. If it's merely stuck (e.g. out of capacity), Oracle may still bring it back later, and it would then poll Telegram with the same tokens. Its boot volume can go too once a clone holds the data.
9. **Clean up the clone** after a few days of normal running: `sudo umount /mnt/old`, detach `old-boot-clone` from the instance, delete it.
10. **Update the VM details** recorded in `docs/HANDOFF.md`.

**If SSH to the new VM times out**: check the Oracle side before debugging the VM. Look at the security list (TCP 22 ingress), the route table (0.0.0.0/0 → internet gateway), and the console history (`oci compute console-history capture`, which shows whether cloud-init and `ssh.service` started). If all of that is fine, test from a different network: in October 2026 the timeouts came from the client's network path, not from the VM. Run Command can reach the VM without SSH, but only after a dynamic group matching the instance plus a policy granting it `use instance-agent-command-execution-family`. It runs as the unprivileged `ocarun` user (no `sudo`), and its text output is truncated after about 1 KB.
