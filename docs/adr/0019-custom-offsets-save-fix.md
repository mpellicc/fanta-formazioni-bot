# ADR 0019: Fix silent custom-offset loss on "Personalizzati" → Salva

- Status: accepted
- Date: 2026-07-11

## Context

ADR 0015 introduced the offsets grid: an 8-bit mask over 8 fixed presets, plus
a "Personalizzati" free-form path (`ConversationHandler`) for values outside
those presets. Because the mask can only represent the 8 presets, any custom
(non-preset) offset saved via free-form input is invisible to it.
`docs/HANDOFF.md` flagged the resulting bug (found 2026-07-08, during
pre-season testing on the mock provider): after submitting a custom value
like `90m` via "Personalizzati", `receive_custom_offsets()`
(`telegram/callbacks.py`) still calls `_restore_grid()`, which puts the
*original* grid message back into an **interactive** state using
`mask_from_offsets(new_offsets)` — necessarily `0` (or missing the custom
bit) since `90m` isn't a preset. If the user later presses **Salva** on that
reopened grid, `save_offsets_callback` rebuilds the whole offset list from
`offsets_from_mask(mask)` alone, silently discarding the just-saved `90m`. A
related minor defect: `_restore_grid` only edits the keyboard, never the
message text, so the "Attualmente arrivano X" line goes stale after a
free-form save.

## Decision

**1. On a successful custom submission, delete the original grid message
instead of restoring it to an interactive state.** `receive_custom_offsets()`'s
success path no longer calls `_restore_grid()`; it deletes the original grid
message (in addition to the existing ForceReply prompt deletion), leaving only
the confirmation reply (`messages.offsets_updated(...)`) already sent in
response to the user's message. This removes the artifact that could reopen
the lossy-mask risk in the first place, and as a side effect fixes the
stale-text bug too — there's no longer a stale message left to view. It
matches the codebase's existing convention of deleting the ForceReply prompt
on back/cancel/timeout; deleting the grid message on success is the same
pattern applied to the other now-disposable message in the flow.

**2. "⬅️ Indietro", `/annulla`, and the conversation timeout are unchanged**:
they still restore the interactive grid using the *original*, pre-attempt
mask (`context.user_data[_GRID_MASK]`), which stays accurate since no data
was changed on those paths.

**3. Fresh `/personalizza_orari` invocations while a subscription already
holds non-preset offsets are explicitly out of scope for this fix.** The grid
still opens with a mask that can't represent those values, and pressing
Salva there can still silently drop them (`save_offsets_callback` fully
replaces from the mask alone). This is a real, narrower residual risk —
Matteo decided (2026-07-11) to leave it as a known limitation for now rather
than also making `save_offsets_callback` merge-safe, to keep this fix scoped
to the concretely reported/reproduced bug. Revisit if it turns out to bite in
practice.

**4. No additional visual hint in the grid text.** `offsets_usage()`'s
"Attualmente arrivano X" line already always reflects the true, complete
subscription state (preset + custom) — it reads from the DB, not from the
mask — so no extra caption is added.

## Alternatives considered

- **Merge semantics in `save_offsets_callback`** (grid Save only adds/removes
  checked presets, preserving any existing non-preset values): would also
  cover the fresh-invocation residual case (Decision 3), but is a bigger,
  more structural change to Save's semantics; deferred per Matteo's scope
  call for this pass.
- **Explicit confirmation before an overwriting Save**: adds a new UI
  step/state for a narrower benefit than deletion-on-success; not pursued.
- **Blocking the grid entirely whenever non-preset offsets exist**: reduces
  the grid's usefulness even for unrelated preset tweaks; not pursued.

## Consequences

- `telegram/callbacks.py`: `receive_custom_offsets()` deletes the original
  grid message on success instead of calling `_restore_grid()`; a new
  `_close_custom_offsets()` helper does the deletion. `back_from_custom_offsets`,
  `cancel_custom_offsets`, `timeout_custom_offsets` are unchanged.
- The "Salva sovrascrive i custom" bug (`docs/HANDOFF.md`) is fixed for the
  reported flow (Personalizzati → submit → later Salva on the reopened grid);
  the fresh-invocation variant (Decision 3) remains a known limitation, noted
  in `docs/HANDOFF.md`.
- No change to `messages.py`, `keyboards.py`'s mask logic, or the DB schema.
