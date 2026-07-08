# ADR 0011: Manual-bump releases via "Prepare release" workflow

- Status: **superseded by ADR 0017** (2026-07-08) — trunk-based development with
  tag releases replaces the `dev`/`main` release-PR flow described below. Kept
  for history; do not follow this ADR for new work.
- Date: 2026-07-07

## Context

With the dev/prod split (ADR 0010), production releases are PRs `dev` → `main`. Versions should advance on every release with an explicit choice of patch/minor/major, and each release should leave a traceable trail: version in `pyproject.toml`, git tag, GitHub Release, and a version-tagged Docker image.

## Decision

Releases are prepared by a manual workflow and finalized by the deploy pipeline:

1. **`release-prep.yml`** (workflow_dispatch on `dev`, input: `patch`/`minor`/`major`): bumps the version with `uv version --bump`, commits `Release vX.Y.Z` to `dev`, and opens the release PR `dev` → `main`.
2. **`deploy.yml`** on `main`: builds the image tagged `:latest`, `:<sha>` **and `:X.Y.Z`**; after a successful production deploy, the `release` job creates the git tag `vX.Y.Z` and the GitHub Release with auto-generated notes (idempotent: skipped if the tag exists).

`pyproject.toml` is the single source of truth for the version; tags and image labels are derived from it.

## Alternatives considered

- **Conventional commits + semantic-release**: fully automatic, but the bump is decided by commit message discipline rather than an explicit choice at release time.
- **Label on the release PR**: bump happens on `main` after merge, requiring an automatic back-merge of the version commit into `dev`.

## Consequences

- The GitHub Release exists only after the production deploy succeeded — a release implies "in production".
- PRs opened by `GITHUB_TOKEN` don't trigger CI; the release PR shows no checks (the same code already passed CI on `dev`, only the version line differs). Requires "Allow GitHub Actions to create and approve pull requests" enabled in repo Actions settings.
- Hotfix flow stays the same: fix on `dev`, run Prepare release with `patch`.
