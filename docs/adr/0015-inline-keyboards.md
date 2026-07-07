# ADR 0015: Inline keyboards for subscription and reminder-offset management

- Status: accepted
- Date: 2026-07-07

## Context

`/promemoria_on`, `/promemoria_off`, `/promemoria` and `/personalizza_orari`
(ADR 0012/0013) are text-only. This ADR adds `InlineKeyboardMarkup` +
`CallbackQueryHandler` buttons on top of the same commands, without changing
their text form or the underlying `subscriptions` model (ADR 0008). It was
picked as the next roadmap item (`docs/HANDOFF.md`) ahead of user-owned
channels.

## Decision

**1. Surfaces.** `/start` and `/promemoria` gain a toggle button
(🔔 Attiva / 🔕 Disattiva, mirroring whichever action the chat can currently
take); `/personalizza_orari` with no arguments shows a preset picker instead
of only the usage text.

**2. Admin enforcement is repeated on callbacks.** Buttons appear in both
private chats and groups (consistent with where the commands already work).
In groups any member can press a button, so
`_sender_may_manage_subscription` (`telegram/commands.py`) is generalized to
accept a `(user, chat)` pair usable from both `Message` and `CallbackQuery`;
a rejected press gets `answer_callback_query` with the existing
`messages.admin_only()` text as a toast, not a new message.

**3. Preset picker, not free-form buttons.** Offsets are seconds-granular and
buttons can't take arbitrary input, so the grid offers 8 fixed presets:
**2 giorni, 24h, 12h, 3h, 1h, 30 minuti, 10 minuti, 5 minuti** — chosen to
avoid two failure modes: an offset that fires before the previous matchday's
deadline has even passed (rules out 7 giorni), and gaps a real user
wouldn't want (rules out 6h, keeps a tighter spread instead). Each preset is a
toggle (✓ when selected); state travels in `callback_data` as a 8-bit mask
(`off:t:<index>:<mask>`) — **stateless**, no new table or `bot_data` entry, so
a stale keyboard from a restarted bot still round-trips correctly. Saving
(`off:save:<mask>`) writes exactly the checked presets; a mask of 0 is
rejected client-side (button re-rendered, no save) the same way an empty
`/personalizza_orari` argument list is today.

**4. "Personalizzati" opens a short conversation for free-form input**, since
the grid cannot express values outside the 8 presets (e.g. `2g,12h,10m` mixed,
or a value the grid doesn't offer). Implemented as a `ConversationHandler`:

- The `off:custom` button edits the grid message into a "waiting" state
  (single **⬅️ Indietro** button, `off:back`) and sends a *second* message
  with `ForceReply(selective=True)`, since a `ForceReply` and an inline
  keyboard cannot live on the same message. That prompt's text explicitly
  spells out the mechanism ("rispondi a questo messaggio con gli orari, es.
  `2g,12h,10m`") — Group Privacy mode (kept ON, `docs/HANDOFF.md`) means the
  bot only sees replies to its own messages in groups, so without this
  explanation a group member has no way to discover that a plain message
  won't reach the bot.
- Input is parsed with the existing `parse_offsets_args`
  (`telegram/commands.py`); errors re-prompt in place instead of ending the
  conversation.
- Exits: **⬅️ Indietro**, `/annulla`, or a ~5 minute timeout — all delete the
  prompt message and restore the grid on the original message.

**5. Units shown to users drop to `m`/`h`/`g`.** A reminder a few seconds
before the deadline is not a realistic use case (`MIN_OFFSET` is already 1
minute), so `s` disappears from help text, error messages, and examples.
`parse_duration` (`config.py`) keeps accepting `s` — it's parsing surface
already shipped in v0.11.0 for `REMINDER_OFFSETS`/`/personalizza_orari`, and
removing it would be a silent breaking change for no benefit. `parse_duration`
gains `g` (86400s) as a new accepted unit, additive to the existing `s`/`m`/`h`
map.

**6. Edit in place.** Every callback ends with `edit_message_text` or
`edit_message_reply_markup` (never a new message) plus `answer_callback_query`
as the toast. `BadRequest: message is not modified` (double-press on an
already-current state) is caught and ignored — the source of truth is always
the DB read at the start of the handler, never the pressed button's assumed
prior state.

**7. `CallbackQueryHandler` needs its own `ALLOWED_CHAT_IDS` gate.** PTB's
chat filters apply to `Message`-based handlers only; the dev bot's existing
silence-outside-allowed-chats behavior (`app.py`) is replicated with a manual
`chat.id in settings.allowed_chat_ids` check at the top of the shared callback
entry point, matching the existing `filters.Chat` behavior on commands.

## Alternatives considered

- **State in `bot_data` or a new DB column** instead of encoding it in
  `callback_data`: survives longer messages but is lost on restart (`bot_data`)
  or needs a schema change (DB) for a value that's cheap to round-trip in 64
  bytes of `callback_data`.
- **A handful of one-tap preset combinations** (e.g. "24h+1h+5m",  "solo 1h")
  instead of a multi-select grid: fewer buttons, but far less flexible — real
  usage already varies per subscription (that's the point of ADR 0013), and a
  fixed combo list would just push most users back to the text command anyway.
- **New message instead of edit-in-place**: simpler (no `BadRequest` handling),
  but leaves stale buttons in the chat that no longer reflect the real
  subscription state, and clutters groups over a matchday's several presses.
- **Dropping `s` from `parse_duration` entirely**: consistent with the new
  user-facing units, but breaks any existing `REMINDER_OFFSETS`/offsets row
  already using seconds — no reason to make it a breaking change.

## Consequences

- New modules: `telegram/keyboards.py` (pure: presets, mask math, keyboard
  builders) and `telegram/callbacks.py` (`CallbackQueryHandler` entry points +
  the custom-offsets `ConversationHandler`). `commands.py`'s subscribe/
  unsubscribe/set-offsets logic is factored so both the command and the
  callback path call the same repository + `reschedule_reminders` code.
- `messages.py` gains button labels and the custom-input prompt/cancel/timeout
  texts; `/help` documents the buttons and, explicitly, how replying to the
  custom-input prompt works in groups.
- No BotFather setting changes (buttons are pure PTB), unlike the user-owned
  channels idea which needs Channel Admin Rights.
