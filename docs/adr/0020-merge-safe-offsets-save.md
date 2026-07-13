# ADR 0020: Merge-safe Salva on the offsets grid

- Status: accepted
- Date: 2026-07-13

## Context

ADR 0019 fixed the concretely reproduced "Salva sovrascrive i custom" bug
(Personalizzati → submit → Salva on the reopened grid), but explicitly left
open a narrower residual case (Decision 3): the offsets grid is an 8-bit mask
over `OFFSET_PRESETS` (`telegram/keyboards.py`), so any non-preset offset
(e.g. `90m`, saved via free-form "Personalizzati" input) is invisible to the
mask. If a subscription already holds such a custom offset and the user opens
`/personalizza_orari` **fresh** (not via the just-fixed flow), the grid still
renders with a mask that can't represent it, and `save_offsets_callback`
(`telegram/callbacks.py`) rebuilds the whole offset list from
`offsets_from_mask(mask)` alone — a Salva on unrelated preset toggles silently
discards the custom value.

ADR 0019 deferred this to keep that fix scoped to the reported bug, planning
to revisit "if it turns out to bite in practice." Ahead of the 1.0 release
(target: prod before the 2026-08-22 season start), Matteo decided to close it
now rather than ship with a known silent-data-loss path.

## Decision

**Make `save_offsets_callback` merge-safe: Salva only adds/removes the
preset toggles shown in the grid; any already-saved non-preset offset is
preserved automatically.**

- New pure helper in `telegram/keyboards.py`, alongside `mask_from_offsets`/
  `offsets_from_mask`: `non_preset_seconds(offsets_seconds)` returns the
  subset of offsets (in seconds) that are **not** one of `OFFSET_PRESETS`.
- `save_offsets_callback` (`telegram/callbacks.py`) reads the chat's current
  subscription (`repository.get_subscription`), computes
  `preserved = non_preset_seconds(existing.reminder_offsets)`, and merges it
  with the preset offsets decoded from the mask before calling `set_offsets`.
  The empty-selection guard (`offsets_selection_empty`) now checks the
  **merged** result, not the mask alone — a Salva that keeps only preserved
  custom offsets (no preset checked) is legitimate and must not be rejected.
- The confirmation text (`messages.offsets_updated`) reflects the real merged
  result, matching what `offsets_usage()` already shows (it reads the DB, not
  the mask).
- `receive_custom_offsets`'s `_close_custom_offsets` (ADR 0019 Decision 1,
  deletes the grid message after a successful free-form submission) is
  unchanged — it still works, and remains a reasonable UX choice, but its
  original motivation (avoiding the lossy-mask reopen risk) is now redundant:
  even if the grid were left open, a subsequent Salva would no longer drop the
  custom value.

**Tradeoff accepted**: the grid can no longer *remove* a non-preset custom
offset — only "Predefiniti" (full reset) or a new "Personalizzati" submission
(which fully replaces the list, per existing behavior) can. This was already
identified as the tradeoff of the "merge semantics" alternative in ADR 0019
and is preferred over silent loss.

## Alternatives considered

Same as ADR 0019's "Alternatives considered" section (explicit confirmation
before an overwriting Save; blocking the grid entirely when non-preset
offsets exist) — not revisited here, as merge semantics was already the
preferred alternative there, only deferred for scope reasons.

## Consequences

- `telegram/keyboards.py`: new pure helper `non_preset_seconds`, unit-tested
  directly (no Telegram/network dependency).
- `telegram/callbacks.py`: `save_offsets_callback` reads the DB before
  writing (previously write-only from the mask); behavior for
  subscriptions with only preset offsets is unchanged.
- The known limitation recorded in ADR 0019 Decision 3 is closed; the residual
  gap noted there (fresh `/personalizza_orari` opening with an unrepresentable
  mask) no longer causes data loss.
- No DB schema change.
