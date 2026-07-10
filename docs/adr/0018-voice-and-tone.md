# ADR 0018: Voice & tone for user-facing copy

- Status: accepted
- Date: 2026-07-10

## Context

All user-facing texts live in `telegram/messages.py` (Italian, HTML parse
mode), with button labels in `telegram/keyboards.py` and the dynamic value
rendering in `format.py`. They were written incrementally across ADRs
0012–0016 and are correct and clear, but the voice was never defined on
purpose: it drifted to a generic-friendly utility tone.

The v1.0 roadmap (`docs/HANDOFF.md`) calls for a copy revision pass before the
production release (target: season start, 22 Aug 2026). Rather than a one-off
rewrite, this ADR fixes a **voice & tone** so the same personality carries
forward to the surfaces still to come (user-owned channels, inline mode). It
also records the boundaries so the copy stays consistent and doesn't need to be
re-litigated each time a new string is added.

## Decision

**1. Voice: goliardico-fantacalcistico, medium intensity, clean.** The bot
talks like a slightly cheeky fantacalcio "mister": second person singular
("tu"), light dressing-room ribbing, football-league flavour. Personality is
strongest on the "warm" messages (`start`, `reminder`, subscription
confirmations); "cold" messages (deadline info, errors, admin-only) stay
informative with at most a small guizzo. **Clean**: no profanity — the official
channel `@fantaformazionireminders` is public.

Rejected: *leggero* (too close to the current bland tone) and *spinto*
(profanity-adjacent, denser jargon, ages worse and risks tone in a public
channel).

**2. Information before the joke (guardrail).** A message must remain
actionable if the reader ignores the humour. The deadline card
(`next_deadline`), the reminder (`reminder`), and every error/usage message
keep the concrete facts — round, date, time, remaining duration, what went
wrong, what to type — unambiguous and up front. The joke seasons, it never
replaces the instruction. Error messages in particular stay useful first,
funny a distant second.

**3. Lexicon.** Prefer, in moderation (not every line):

| Prefer | Meaning / use |
|---|---|
| **mister** | the reader (occasional vocative, not every message) |
| **schierare / schiera i titolari** | set the lineup (already used) |
| **panchina, panchinaro** | benched, mild ribbing |
| **il -1 (d'ufficio)** | the auto-penalty for a missing lineup — the stakes |
| **fischio d'inizio / si chiude** | the deadline moment |
| **giornata** | matchday (existing) |

Avoid: forced or dense slang, regionalisms, anything that needs fantacalcio
insider knowledge to parse a *critical* instruction.

**4. Emoji: a semantic convention plus a small tonal set, density kept low.**
Two categories, never more than **one emoji per line** and no message a
Christmas tree.

*4a. Functional emoji* — one per function, reused consistently, not decoration:

- 🚨 reminder urgency · 📅 matchday · ⏰ deadline · ⚽ football/lineup theme
- ✅ activation/confirmation · 🔔 enable toggle · 🔕 disable toggle
- ✏️ free-form input · 💾 save · ↩️ default/reset · ⬅️ back · 👋 greeting

⚽ marks the football/formation theme itself (bot identity, the act of
schierare) — e.g. the `start` header or a line about the lineup — where 📅
(matchday) and ⏰ (deadline) don't already carry the meaning. It stays a marker,
not a bullet decoration.

*4b. Tonal faces* — a curated set to land the goliardico voice, used
**sparingly** and only on *warm/playful* messages (start, reminder,
subscription confirmations, teasing lines). **Never** on cold or error/usage
messages — that would undercut the information-before-the-joke guardrail
(Decision 2). Allowed set, picked for the register:

- 😉 complicity / light sfottò · 😏 smug · 😅 self-irony / near-miss · 🙌 celebration

Rule of thumb: a tonal face is optional seasoning at the end of a playful line,
at most one per message, and if removing it changes nothing about what the user
must do, it's in the right place.

**5. HTML formatting conventions (unchanged, made explicit).** `<b>` for the
key dynamic values (times, durations, matchday, on/off state); `<code>` for
copy-pasteable examples and command syntax; `html.escape` on any user-echoed
value (e.g. invalid offset tokens). HTML parse mode only, never MarkdownV2.

**6. Recurring micro-patterns may vary, within limits.** Boilerplate repeated
verbatim today ("prima di ogni scadenza", "in questa chat", "Usa /x per…") may
be reworded for rhythm so the bot doesn't read like a form letter — but the
*meaning* stays identical and unambiguous. Consistency of meaning over
consistency of exact wording.

**7. `format.py` value rendering stays neutral and precise.** The voice lives
in the surrounding sentences, not in the numbers. `format_date`,
`format_time`, `format_remaining`, `format_duration`, `join_list` keep
rendering values exactly and soberly ("1 giorno e 3 ore", "24 → 1 giorno"): a
reminder's whole job is an unambiguous time, and `test_format.py` pins this
behaviour. `format.py` is in scope only to confirm this boundary — no
behavioural change is planned there, so its tests stay green.

**8. Scope of the pass.** Rewrite `telegram/messages.py`; update the button
labels in `telegram/keyboards.py` to match (deduplicated per Decision 10);
produce a refreshed **BotFather command-description list** as pasteable text
(out-of-repo, applied by hand on both dev and prod bots), plus **About**/
**Description** texts (same, out-of-repo). No handler, callback_data, or
scheduling logic changes. The code touched beyond copy: the `reminder()`
selector (Decision 9) and its new `Settings.urgent_reminder_threshold` field
(Decision 9) — a config addition, not a data-model change.

**9. Reminder copy: a rotating pool for the "early" reminders, a fixed template
for the "last-call" ones.** The `reminder` message splits by how close the
offset is to the deadline:

- **Early reminders (offset > 10 minutes)** draw from a **pool of variants**
  (~6 to start, extensible), so a user watching several matchdays doesn't read
  the same line every time. Selection is **deterministic** — a hash of
  `(round, offset)` mod pool size, not random: the same `(round, offset)`
  always picks the same variant, which keeps it trivially testable and gives
  good variety across matchdays *and* between the multiple early reminders
  within one matchday in practice. This is **not a formal
  no-adjacent-repeat guarantee**: a true guarantee would require each
  reminder to know its rank among that chat's configured offsets (e.g. via a
  new `PlannedReminder` field set by the planner), which is a model change
  this ADR deliberately keeps out of scope (Decision 8, copy-only pass) —
  an occasional repeat between two reminders of the same matchday is an
  accepted, low-stakes trade-off. Every variant follows the medium/clean
  voice (Decisions 1–4) and keeps the concrete facts (round, deadline,
  remaining time) up front (Decision 2).
- **Last-call reminders (offset ≤ 10 minutes)** use a **single, fixed,
  unmistakable template** with a genuinely urgent tone and a stable visual
  signature (e.g. ⏰🚨 + "ULTIMA CHIAMATA"). It never rotates — repetition *is*
  the point: it trains the reflex "quando vedo *questo* messaggio, controllo
  subito la formazione." No tonal faces here (Decision 4b): urgency only.

The threshold is a `Settings` field, `urgent_reminder_threshold`
(env `URGENT_REMINDER_THRESHOLD`, default `10m`), not a hardcoded constant —
it follows the same `parse_duration`/`field_validator` pattern as
`deadline_margin` and `mock_kickoff_offset` (`config.py`). Despite living in a
copy-focused ADR it's an operational knob (which presets count as "last-call"),
not a voice choice, so it belongs where the other timing knobs already are;
`messages.reminder()` takes it as an explicit parameter rather than reading a
module constant, keeping the function pure and testable with any threshold.
It's inclusive, and independent of the preset grid so it classifies custom
offsets too. `reminder()` gains the offset and the threshold as parameters to
branch on; `reminders/jobs.py` already carries `offset_seconds` in the job and
reads `settings.urgent_reminder_threshold`, passing both at the call site.

**10. Button-label wording lives once, in `keyboards.py`.** `keyboards.py`'s
button text (`Attiva/Disattiva promemoria`, `Salva`, `Predefiniti`,
`Personalizzati`, `Indietro`) and the handful of `messages.py` sentences that
name those same buttons in prose ("premi **Salva**", "il bottone **Indietro**")
were independently hand-written strings with no link between them — exactly
the drift risk flagged when reviewing this ADR. Fix: `keyboards.py` exports
plain `str` constants (`ACTION_SUBSCRIBE`, `ACTION_SAVE`, `ACTION_DEFAULTS`, …)
next to the builders that already own callback_data/preset logic for these
buttons, and composes them with the button emoji; `messages.py` imports
`keyboards` for the handful of sentences that mention a button, interpolating
the same constant. Button wording is kept in `keyboards.py` rather than
`messages.py` because it's the button's own domain (colocated with its
callback_data and builder) — this narrows the blanket "all user-facing texts
live in `messages.py`" rule from `CLAUDE.md` into "message bodies in
`messages.py`, button labels in `keyboards.py`, each imported by the other
where needed"; `CLAUDE.md`'s invariant line is updated to match. Deliberately
**not** a JSON/i18n-style catalog with string-keyed lookups: this project has
exactly one language and is `mypy --strict` end to end, so a data-file layer
would trade compile-time-checked constants for a stringly-typed lookup and an
interpolation layer to reimplement HTML-escaping/dynamic values that plain
f-strings already give for free, for ~30 total strings. Revisit only if the
string count or a real multi-language need grows enough to justify it.

## Anchor examples (before → after, medium/clean)

Reminder:

> **Before:** 🚨 <b>Ricordati di schierare la formazione!</b> 🚨 … Hai ancora <b>1 giorno e 3 ore</b>!
>
> **After:** 🚨 <b>Mister, la formazione non si schiera da sola!</b> 🚨 … Ancora <b>1 giorno e 3 ore</b>: niente scuse e niente titolari a sorpresa in panchina 😉

Start (⚽ marks the football/lineup theme on the identity line — moved after the
bot's name per the 2026-07-10 feedback pass, see Amendment below):

> **After:** Ciao, mister! Sono <b>Fanta Formazioni Bot</b> ⚽ e ti tengo sveglio prima di ogni scadenza, così non schieri più mezza squadra in panchina.

Reminder split (Decision 9) — one early pool variant vs the fixed last-call:

> **Early (e.g. 24h), pool variant:** 📅 <b>Giornata 12</b>, tra <b>1 giorno</b> si chiude. Occhio a squalificati e diffidati, mister — la panchina non fa punti 😉
>
> **Last-call (≤ 10 min), fixed template:** ⏰🚨 <b>ULTIMA CHIAMATA — Giornata 12</b> 🚨⏰ Scadenza alle <b>18:25</b>, restano <b>meno di 10 minuti</b>. Schiera la formazione <b>ORA</b>.

Empty selection error (guardrail — still instructional):

> **Before:** Seleziona almeno un orario prima di salvare.
>
> **After:** Serve almeno un orario prima di salvare, mister: tocca una casella.

The full rewrite is applied in the implementation step, message by message,
against these rules.

## Alternatives considered

- **One-off rewrite without an ADR** — faster, but the voice would stay
  implicit and drift again as new surfaces (channels, inline mode) are added.
- **Leggero / spinto intensity** — see Decision 1.
- **Push the voice into `format.py`** (playful durations/relative time) —
  rejected: the dynamic values must read unambiguously, and it would churn
  `test_format.py` for no user benefit.
- **Random pool selection** (Decision 9) — simpler, but not reproducible in
  tests; deterministic hashing keeps the same "not always identical" benefit
  while staying testable, at the cost of the same non-zero repeat probability
  either approach has without per-chat rank tracking.
- **Rank-based selection with a `PlannedReminder` field** (Decision 9) — the
  only way to formally guarantee no adjacent repeat, rejected for this pass
  as a model change outside the declared copy-only scope; revisit if the
  occasional repeat turns out to bother users in practice.
- **Rotating the last-call message too** — rejected: variety defeats the
  recognition/routine goal; the last-call template is deliberately identical
  every time.

## Consequences

- `telegram/messages.py` largely rewritten; `telegram/keyboards.py` labels
  adjusted; `/help` and `/start` re-voiced. No tests assert on these strings
  today (only `test_format.py`, unaffected), so the suite stays green.
- A new BotFather command-description list is delivered as text and must be
  pasted on **both** dev and prod bots (menu descriptions only; enforcement
  stays in code).
- About/Description texts are delivered as text too, same manual-paste flow,
  with a tagged variant on the dev bot (`⚠️ BOT DI TEST — non è quello
  ufficiale`) so it can't be mistaken for the production bot if ever shared.
- `messages.py` grows a `REMINDER_POOL` (early-reminder variants) and a fixed
  `reminder_urgent`; `reminder()` becomes an offset-and-threshold-based
  selector. `config.py` gains `Settings.urgent_reminder_threshold` (env
  `URGENT_REMINDER_THRESHOLD`, default `10m`); `reminders/jobs.py` reads it
  and passes both it and the existing `offset_seconds` into the message
  builder. `keyboards.py` gains the `ACTION_*` button-label constants
  (colocated with its builders/callback_data); `messages.py` imports
  `keyboards` for the sentences that name a button.
- `CLAUDE.md`'s "user-facing texts live only in `messages.py`" invariant is
  narrowed to "message bodies in `messages.py`, button labels in
  `keyboards.py`" (Decision 10) to match.
- This ADR is the reference for any future user-facing copy; new strings follow
  its lexicon, emoji convention, and the information-before-the-joke guardrail.

## Amendment (2026-07-10): first manual-testing feedback pass

Matteo's first read-through of the rewritten copy (still pre-merge) produced
concrete notes, applied as follow-up edits:

**1. Legacy vs. promoted commands.** `/promemoria_on`, `/promemoria_off`, and
`/personalizza_orari` *with raw arguments* are the pre-ADR-0015 text-only
interface; the inline-keyboard flows (`/promemoria`'s toggle button,
`/personalizza_orari`'s grid, `/start`'s toggle) are what the bot now promotes.
Going forward, prose outside `/help` avoids naming a legacy command as the
suggested action — `/help` remains the one place that lists every command
explicitly, since it's the technical reference surface. Where a message needs
to point somewhere, it points to the promoted command (`/promemoria`, not
`/promemoria_on`/`/promemoria_off`) or drops the explicit command entirely
when a button is already visible on the same message. Concretely:
`subscription_disabled()`'s joke keeps its 😏 but now redirects to
`/promemoria` instead of `/promemoria_on`; `subscription_not_enabled()` drops
its call-to-action outright (most of its call sites already render a toggle
button alongside it); `subscription_enabled()`/`subscription_status()` drop
their trailing "usa /promemoria_off" line for the same reason; `start()` drops
its "oppure usa /promemoria_on" sentence since the subscribe/unsubscribe
button sits right below it in the same message.

**2. `/help` dials back to purely informational.** As the one surface meant to
read like technical reference rather than personality, its intro reverts from
"Ecco il regolamento, mister" to the plain "Ecco cosa posso fare" — no
lexicon, no vocative, matching Decision 2's "cold messages stay informative"
more strictly than the rest of the voice.

**3. Reminder-offset lists render as an actual bullet list, not inline
prose.** Every message that shows a chat's configured reminder offsets
(`subscription_enabled`, `subscription_already_enabled`, `subscription_status`,
`offsets_usage`, `offsets_updated`, `offsets_reset`) switches from one
`fmt.join_list`-joined sentence ("arrivano **24 ore, 1 ora e 5 minuti**") to a
lead-in line plus a `•`-per-line list (Telegram HTML has no real `<ul>`/`<li>`,
so plain-text bullets are the only option, matching the pattern `/help`
already used for its command list). `_offsets_line` is replaced by
`_offsets_list`, used everywhere the old helper was.

**4. `format_remaining` (`format.py`) now scales past 7 days** — amending
Decision 7's claim that "no behavioural change is planned there": weeks (7
days) and months (a flat 30-day approximation, display-only, never used for
scheduling) become the top unit for deadlines further out, followed by up to
two of the existing day/hour/minute units for the remainder, e.g. "1 mese, 12
giorni e 23 ore" or "2 settimane e 14 ore"; below 7 days, output is byte-for-byte
unchanged (verified against the pre-existing `test_format_remaining_two_largest_units`
without editing it). `next_deadline()` and `reminder()`'s callers get this
automatically since both already call `fmt.format_remaining`. `next_deadline()`
also drops its trailing ⚽ (Matteo: "for the rest, remove the ball" — the
football theme is already carried by 📅/⏰ there, per Decision 4a's own rule
that ⚽ only marks the theme where those two don't already cover it).

**5. `/start`'s ⚽ moves after "Sono Fanta Formazioni Bot"**, not before, and
the bot's display name is spelled with a space — "Fanta Formazioni Bot" — a
branding change decided during this same session (fixed opportunistically
wherever prose is touched from here on, not a repo-wide sweep).

No handler, model, or scheduling changes; `config.py`/`format.py` gain no new
settings from this amendment (only the one already added in Decision 9). All
four checks green; `test_format.py` needed no edits since the sub-7-day
behaviour it pins is unchanged.
