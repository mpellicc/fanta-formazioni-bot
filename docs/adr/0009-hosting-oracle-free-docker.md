# ADR 0009: Hosting on Oracle Cloud Always Free, Docker + GHCR + GitHub Actions

- Status: accepted
- Date: 2026-07-06

## Context

v1 ran as a bare systemd daemon on a paid VPS that no longer exists. Requirements: always-on process (long polling + scheduled jobs), tiny persistent SQLite file, cost as close to zero as possible.

## Decision

- **Oracle Cloud Always Free** Ampere (ARM) VM as the runtime host: genuinely free forever, always-on, same operational model as a VPS.
- The bot runs as a **Docker** container (`linux/arm64` image) with the SQLite file on a named volume, `restart: unless-stopped`.
- **CI**: GitHub Actions runs ruff + mypy + pytest on every push/PR.
- **CD**: on push to `main`, an image is built for arm64, pushed to **GHCR**, and the VM pulls and restarts via SSH (`docker compose pull && up -d`).

## Alternatives considered

- **Fly.io machine + volume**: excellent DX, ~€2–3/month; rejected only on cost.
- **Cloudflare Workers + Cron + D1**: truly serverless and free, but incompatible with python-telegram-bot and best served by TypeScript — a much more radical rewrite.
- **Keep a paid VPS**: no longer exists; recreating one costs money for no advantage over the free tier.

## Consequences

- Images must be built for `linux/arm64` (Ampere CPUs); CI uses buildx.
- VM creation and first-time setup are manual, documented in [docs/DEPLOY.md](../DEPLOY.md).
- If Oracle ever reclaims the free tier, the container runs unchanged on any Docker host.
