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

## Amendment (2026-10-06): Pay As You Go tenancy, still Always Free

An Always Free account gets the lowest priority for capacity. A1 was out of capacity at launch, so the bot ran on an x86 `E2.1.Micro` instead (hence the multi-arch image). On 2026-10-01 that VM's host failed (Oracle notice COMPUTE-12D). Oracle could not relocate it because Milan had no Micro capacity left, so it stayed stopped and prod was down until 2026-10-06.

**Decision**: the tenancy is upgraded to **Pay As You Go**, which gets priority access to capacity, including A1. The bot moves to a `VM.Standard.A1.Flex` (1 OCPU / 6 GB, ARM) with a **reserved** public IP. The intent of this ADR does not change: the bot must cost nothing. Always Free resources stay free on a PAYG tenancy, and the footprint stays well inside the Always Free limits (A1: 3,000 OCPU-hours + 18,000 GB-hours per month; storage: 200 GB total across boot and block volumes).

**Guardrail**: a budget on the root compartment (€1/month, alert when actual spend reaches 1%) emails as soon as anything billable appears. A PAYG tenancy no longer refuses paid resources, so this alert replaces that protection. Any extra instance, volume or non-free shape must be a deliberate choice, not an accident.

**Consequences**:
- A billable mistake is possible now, and the budget alert is what catches it. Check the alert still exists after any billing or tenancy change.
- Temporary resources (e.g. a boot-volume clone used for data recovery) count against the 200 GB storage allowance. Delete them once they've served their purpose.
- The arm64 image built since day one now runs in production, and the x86 build is kept as the fallback for an E2 host.
