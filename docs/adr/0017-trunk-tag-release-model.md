# ADR 0017: Trunk-based development with tag releases and a seasonal maintenance branch

- Status: accepted
- Date: 2026-07-08
- Supersedes: ADR 0011 (release/versioning). Amends: ADR 0010 (dev/prod environments).

## Context

ADR 0011 set up a GitFlow-lite flow: `dev` (default, integration) mirrored to
`main` (production) via a release PR merged with a merge commit. Two problems
surfaced in practice:

1. **`main` accumulates empty merge commits** and always shows "ahead" of `dev`,
   even when their content is identical. `git describe main` is polluted
   (`v0.12.1-4-g…`) while `git describe dev` is clean (`v0.12.1`) — the version
   truth already lives on the integration branch, not on `main`.
2. The model has **no place for seasonal maintenance**. The bot serves one Serie
   A season at a time: once 1.0 ships in August, we want a stable line that
   receives *only* bugfixes discovered during the season, while development of
   the next version continues independently.

Large projects solve both by **trunk + tags** (one long-lived line, releases are
tags — Linux, Kubernetes, Node, Postgres) plus **maintenance branches** cut from
the trunk for the stable line being supported (Kubernetes `release-1.29`, Node
`v20.x`, Postgres `REL_16_STABLE`). We adopt that.

## Decision

**1. `main` becomes the trunk and the default branch; `dev` is retired.**
Active development happens on `main`. Feature branches → PR into `main` (squash
merge, unchanged from ADR 0011's per-feature squash). There is no second
"production mirror" branch, so the ahead/behind divergence disappears.

**2. Releases are git tags `vX.Y.Z`; the tag is the single source of truth for
the version.** No `pyproject.toml` version-bump commit and no "Prepare release"
PR. CI derives everything version-related (image tag, git tag, GitHub release)
from `github.ref_name` on a tag push.

**2a. The project stops being built/distributed as a package (it becomes a uv
"virtual" project); `pyproject.toml` no longer declares a `version`.** The bot
is run as an application (`python -m fantaformazionibot`), never installed from
PyPI nor imported as a library, and nothing in the code reads its own version —
so a static `version` field is dead metadata that can only drift from the tag.
We remove it (and the `[build-system]`), keeping `pyproject.toml` for the
project name, dependencies, and ruff/mypy/pytest config.

- *Implementation note:* the package lives under `src/` (src-layout, which
  assumes installation), so dropping the build means making `src/` importable at
  run time instead. Chosen approach: keep the layout, set `[tool.uv] package =
  false`, and in the `Dockerfile` copy `src/` into the runtime image and run with
  `PYTHONPATH=/app/src` (the builder stage already installs deps-only via
  `uv sync --no-install-project`). `pytest` already sets `pythonpath = ["src"]`;
  local `uv run python -m fantaformazionibot` needs `src` on the path too. This
  must be verified end-to-end (build + run) during implementation.
- *If in-app version reporting is ever wanted* (e.g. a `/version` command),
  inject the tag as a Docker build-arg → env at build time; `hatch-vcs`-style
  VCS versioning is avoided because the Docker build context has no `.git`.

**3. Deployment mapping changes (amends ADR 0010):**
- **Dev bot** deploys on every **push to `main`** (`development` environment,
  `fantaformazionibot-dev`, image `:dev`). The trunk always has a running
  instance to test before a release.
- **Prod bot** deploys on **push of a tag `v*`** (`production` environment,
  `fantaformazionibot`, image `:X.Y.Z` + `:latest`). Prod only moves when a tag
  is cut — an explicit release act, not every commit. Prod keeps running its
  last tag until a new one is pushed.
- The two GitHub environments and their secrets/vars are unchanged.

**4. Seasonal maintenance branch.** When **1.0.0** ships, tag `v1.0.0` on `main`
and cut a long-running branch **`release-1.0`** from that commit. During the
season, prod runs the latest `v1.0.x`. `main` continues toward the next version.

**5. Fix flow during the season: fix on `main` first, then cherry-pick to
`release-1.0`.** A bug is fixed on the trunk (so `main` never regresses), then
the fix is cherry-picked onto `release-1.0` and a patch tag `v1.0.(n+1)` is
pushed, which deploys prod. Release-only fixes (irrelevant to the diverged
trunk) may be committed directly on `release-1.0`.

**6. Workflow changes:**
- `deploy.yml`: trigger on `push` to `main` **and** on `push` of tags `v*`.
  Select environment/dir/image by `github.ref_type` (`tag` → production, else
  → development). The `release` job runs on tag pushes and creates the GitHub
  release from the tag (`gh release create "$ref_name" --generate-notes`); it no
  longer *creates* the git tag (the tag push is what triggered it).
- `release-prep.yml`: the bump-and-open-PR flow is removed. Cutting a release is
  pushing a tag on the right ref (`main` for a new minor/major, `release-1.0`
  for a patch). Optionally kept as a thin `workflow_dispatch` that tags a chosen
  ref, but tagging manually (`git tag vX.Y.Z && git push origin vX.Y.Z`) is the
  baseline.
- Branch protection: protect `main` (default) and, once cut, `release-1.0`.

## Migration runbook (one-time)

**Phase 1 — now, before 1.0 (branch-model switch):**
1. Land this ADR + the `deploy.yml`/`release-prep.yml` rewrite + doc updates via
   a normal feature branch squash-merged into `dev` (the last use of the old
   flow).
2. Reset `main` to `dev`'s tip (`git branch -f main <dev-tip>`; force-push,
   lifting branch protection once). This drops the empty merge commits — content
   is identical (`main` == `dev` == v0.12.1), so nothing is lost; history
   becomes linear with the `v0.12.1` tag at the tip.
3. On GitHub: set the **default branch to `main`**; re-point branch protection to
   `main`; delete the `dev` branch.
4. Prod keeps running its current `:latest` (v0.12.1) — no tag was pushed, so
   nothing redeployed. The next push to `main` redeploys the **dev** bot under
   the new `deploy.yml`.

**Phase 2 — at the 1.0.0 release (before the season, ~August 2026):**
5. Tag `v1.0.0` on `main` and push it → prod deploys 1.0.0, GitHub release
   created. Cut and protect `release-1.0` from that commit; add `release-1.0` to
   `ci.yml`'s `on.push.branches` so cherry-picked fix commits get checked too.
6. `main` moves on toward the next version; season fixes follow decision 5.

## Amendment (2026-08-27): the maintenance line follows the released minor

Decisions 4 and 5 name `release-1.0` and `v1.0.x` literally, because they
assumed one minor would carry a whole Serie A season. `v1.1.0` ships on
2026-08-27, five days into the 2026/27 season, so that assumption is already
spent: the fix it carries (ADR 0023) is a bugfix, but it travels with a new
table and a new external contract (ADR 0024), which is not a `1.0.x` patch.

Generalising, with no change to the model itself:

- The maintenance line is **`release-X.Y` for the minor production currently
  runs**, cut from `main` at that minor's tag — `release-1.1` at `v1.1.0`, and
  so on. Patches for it are `vX.Y.(n+1)` tagged on that branch.
- Cut it **at the tag**, not when it is first needed. The branch's whole
  purpose is to still be there once `main` has moved on; cutting it later means
  cutting it under pressure, from a trunk that already carries unreleased work.
- Decision 5 is unchanged and applies to whichever line is current: fix on
  `main` first, then cherry-pick down. Never the reverse.
- The previous line is retired, not deleted: it stops receiving patches the
  moment its successor is cut, and can be removed at the end of the season.
- A minor **may** ship mid-season. Deploying is a tag push on `main` (decision
  3 keys production off `github.ref_type == 'tag'`, never off a branch), so no
  release branch is needed to reach production — only to go back and patch it.

Step 5 of the runbook — "add the release branch to `ci.yml`" — was never
carried out for `release-1.0`, which therefore took a cherry-picked commit
with no CI run at all. `ci.yml` now matches `release-*` instead of a literal
branch name, so no future line can be forgotten the same way.

## Alternatives considered

- **Keep ADR 0011 (GitFlow-lite, merge commit):** the empty-merge-commit noise
  is cosmetic, but there is still no seasonal maintenance line, which is the
  concrete need here.
- **Fast-forward the release PR into `main`** (keep two mirror branches, no merge
  commit): removes the ahead/behind noise but keeps two branches that must stay
  in lockstep, still offers no maintenance line, and fights GitHub's UI (no FF
  button) and branch protection.
- **Single branch + tags, no maintenance branch:** simplest, but a bugfix found
  mid-season would force shipping it together with whatever unreleased trunk work
  exists — exactly what a frozen `release-1.0` line avoids.
- **Fix on `release-1.0` first, forward-port to `main`:** faster patch turnaround
  but risks forgetting the forward-port and reintroducing the bug on the trunk;
  rejected in favor of fix-on-main-then-cherry-pick.

## Consequences

- `git describe` is clean and meaningful on every branch; the version question is
  answered by tags, never by branch ahead/behind.
- One integration branch instead of two mirrors; releases are explicit tags.
- The bot's version stops living in `pyproject.toml` entirely: the project is no
  longer built as a package (decision 2a), and CI derives every version artifact
  from the git tag. `pyproject.toml` keeps only project metadata + tool config.
- ADR 0011 is superseded; ADR 0010's branch→environment mapping is amended (dev
  bot ← `main`, prod bot ← tags). `CLAUDE.md`, `docs/DEPLOY.md`,
  `docs/HANDOFF.md`, and `README.md` git-workflow sections need updating as part
  of the migration.
- Deploying an old version (rollback) is `git push`-ing/re-pointing to an older
  tag's image, or setting prod's `IMAGE_TAG` to a prior `vX.Y.Z` — cleaner than
  before, since every release is an immutable tagged image.
