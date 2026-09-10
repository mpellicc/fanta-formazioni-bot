"""All user-facing texts (Italian, HTML parse mode). Dynamic values are pre-formatted strings.

Voice & tone: ADR 0018 (goliardico-fantacalcistico, medium intensity, clean).
"""

import html
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from fantaformazionibot import format as fmt
from fantaformazionibot.telegram import keyboards

if TYPE_CHECKING:  # pragma: no cover - import cycle: commands.py imports this module
    from fantaformazionibot.telegram.commands import GroupConfirmResult

OFFSETS_USAGE_EXAMPLE = "/personalizza_orari 24h 1h 5m"

CHANNEL_USERNAME = "@fantaformazionireminders"
MAINTAINER_USERNAME = "@pelliccm"


def start(reminder_offsets: Sequence[timedelta]) -> str:
    offsets = fmt.join_list([fmt.format_duration(offset) for offset in reminder_offsets])
    return (
        "Ciao, mister! Sono <b>Fanta Formazioni Bot</b> ⚽.\n\n"
        "Ti tengo d'occhio le scadenze di ogni giornata di Serie A, così non "
        "schieri più mezza squadra in panchina.\n"
        f"I promemoria arrivano <b>{offsets}</b> prima della scadenza "
        f"sul canale {CHANNEL_USERNAME}: unisciti per non perderti niente!\n\n"
        "Usa /prossima_scadenza per sapere quanto tempo ti resta, "
        "oppure /help per l'elenco dei comandi."
    )


def group_welcome(reminder_offsets: Sequence[timedelta]) -> str:
    """Sent once when the bot is added to a group (ADR 0032). Names the button below
    it rather than a legacy command (ADR 0018 Amendment §1)."""
    offsets = fmt.join_list([fmt.format_duration(offset) for offset in reminder_offsets])
    return (
        "Ciao, mister! Sono <b>Fanta Formazioni Bot</b> ⚽\n\n"
        "Tengo d'occhio le scadenze di ogni giornata di Serie A e avviso qui in gruppo, "
        f"<b>{offsets}</b> prima che si chiuda.\n\n"
        f"Un amministratore pu\u00f2 accendermi col bottone <b>{keyboards.ACTION_SUBSCRIBE}</b> "
        "qui sotto. Con /help vedi tutto il resto."
    )


def help_() -> str:
    return (
        "Ecco cosa posso fare:\n"
        "• /prossima_scadenza — data e ora della prossima scadenza e tempo rimanente\n"
        "• /promemoria_on — attiva i promemoria in questa chat\n"
        "• /promemoria_off — disattiva i promemoria in questa chat\n"
        "• /promemoria — stato dei promemoria in questa chat, "
        "con bottone per attivarli/disattivarli\n"
        "• /personalizza_orari — scegli gli orari dei promemoria da una tastiera di caselle, "
        "oppure passa direttamente gli orari come argomenti\n"
        "• /ho_schierato — silenzia i promemoria residui della prossima giornata; "
        "nei gruppi si fermano quando hanno schierato tutti\n"
        "• /iscrizioni — nei gruppi, chi gioca si registra come manager "
        "(serve al conteggio di /ho_schierato)\n"
        "• /start — presentazione del bot\n"
        "• /help — questo messaggio\n\n"
        "Nella tastiera di /personalizza_orari, il bottone "
        f"<b>{keyboards.ACTION_CUSTOM}</b> ti fa scegliere "
        "un orario non in lista: rispondi al messaggio che ti invio con un formato come "
        "<code>2g,12h,10m</code> (unità m/h/g).\n\n"
        "Nei gruppi, /promemoria_on, /promemoria_off e /personalizza_orari "
        "sono riservati agli amministratori (anche i bottoni corrispondenti); "
        "chiudere e riaprire le iscrizioni pure. /ho_schierato invece è di tutti.\n\n"
        f"Per segnalazioni o suggerimenti scrivi a {MAINTAINER_USERNAME}."
    )


INLINE_DEADLINE_TITLE = "Prossima scadenza"
INLINE_INVITE_TITLE = "Invita Fanta Formazioni Bot"
INLINE_INVITE_DESCRIPTION = "Condividi il bot: promemoria prima di ogni scadenza"


def inline_invite(bot_username: str) -> str:
    """Body of the inline "invite" card (ADR 0033 §1): the one that turns a share
    into an adoption. bot_username comes from context.bot, never from config."""
    return (
        "⚽ <b>Fanta Formazioni Bot</b>\n\n"
        "Ti avvisa prima di ogni scadenza di Serie A, così non schieri "
        "mezza squadra in panchina.\n"
        f"https://t.me/{bot_username}"
    )


def next_deadline(round_: int, deadline: datetime, now: datetime) -> str:
    return (
        f"📅 <b>Giornata {round_}</b>\n"
        f"⏰ Scadenza formazioni: <b>{fmt.format_date(deadline)} "
        f"alle {fmt.format_time(deadline)}</b>\n\n"
        f"Hai ancora <b>{fmt.format_remaining(deadline, now)}</b> per schierare la formazione."
    )


def no_upcoming_deadline() -> str:
    return "Non ci sono altre giornate in calendario per questa stagione! 🥳"


def _pool_v1(round_: int, date: str, time: str, remaining: str) -> str:
    return (
        "🚨 <b>Mister, la formazione non si schiera da sola!</b> 🚨\n\n"
        f"📅 Giornata {round_} — scadenza <b>{date} alle {time}</b>.\n"
        f"Ancora <b>{remaining}</b>: niente scuse e niente titolari a sorpresa in panchina 😉"
    )


def _pool_v2(round_: int, date: str, time: str, remaining: str) -> str:
    return (
        f"⚽ <b>Giornata {round_} in arrivo!</b>\n\n"
        f"Si chiude <b>{date} alle {time}</b>: hai ancora <b>{remaining}</b> per schierare "
        "gli undici giusti, occhio a squalificati e diffidati."
    )


def _pool_v3(round_: int, date: str, time: str, remaining: str) -> str:
    return (
        "🚨 <b>Promemoria formazione!</b> 🚨\n\n"
        f"📅 Giornata {round_} — scadenza <b>{date} alle {time}</b>.\n"
        f"Mancano <b>{remaining}</b>: il capitano si sceglie ora, mica al fischio d'inizio."
    )


def _pool_v4(round_: int, date: str, time: str, remaining: str) -> str:
    return (
        "⏰ <b>Occhio mister, si avvicina il fischio d'inizio!</b>\n\n"
        f"Giornata {round_}, scadenza <b>{date} alle {time}</b> — "
        f"<b>{remaining}</b> e poi si chiude tutto."
    )


def _pool_v5(round_: int, date: str, time: str, remaining: str) -> str:
    return (
        "🚨 <b>La panchina non fa punti!</b> 🚨\n\n"
        f"📅 Giornata {round_} — scadenza <b>{date} alle {time}</b>.\n"
        f"Hai ancora <b>{remaining}</b> per schierare i titolari 🙌"
    )


def _pool_v6(round_: int, date: str, time: str, remaining: str) -> str:
    return (
        f"⚽ <b>Giornata {round_}: formazione, chi era di turno?</b>\n\n"
        f"Si chiude <b>{date} alle {time}</b>, restano <b>{remaining}</b>: "
        "meglio evitarsi il -1 d'ufficio 😅"
    )


_REMINDER_POOL: tuple[Callable[[int, str, str, str], str], ...] = (
    _pool_v1,
    _pool_v2,
    _pool_v3,
    _pool_v4,
    _pool_v5,
    _pool_v6,
)


def _reminder_pool_index(round_: int, offset_seconds: int) -> int:
    """Deterministic rotation (ADR 0018 §9): same (round, offset) always picks the same
    variant, so behaviour is reproducible and testable without randomness. Good variety
    in practice, not a formal no-adjacent-repeat guarantee (see ADR 0018 §9)."""
    return hash((round_, offset_seconds)) % len(_REMINDER_POOL)


def _reminder_urgent(round_: int, time: str, remaining: str) -> str:
    return (
        f"⏰🚨 <b>ULTIMA CHIAMATA — Giornata {round_}</b> 🚨⏰\n\n"
        f"Scadenza alle <b>{time}</b>, restano <b>{remaining}</b>.\n"
        "Schiera la formazione <b>ORA</b>."
    )


def reminder(
    round_: int,
    deadline: datetime,
    now: datetime,
    offset_seconds: int,
    urgent_threshold: timedelta,
) -> str:
    """Early reminders (offset > urgent_threshold) rotate through a pool of variants; the
    last-call reminders (offset <= urgent_threshold) always use the same fixed, urgent
    template (ADR 0018 §9). urgent_threshold is Settings.urgent_reminder_threshold."""
    time = fmt.format_time(deadline)
    remaining = fmt.format_remaining(deadline, now)
    if offset_seconds <= urgent_threshold.total_seconds():
        return _reminder_urgent(round_, time, remaining)
    date = fmt.format_date(deadline)
    variant = _REMINDER_POOL[_reminder_pool_index(round_, offset_seconds)]
    return variant(round_, date, time, remaining)


def lineup_confirmed(round_: int) -> str:
    return (
        f"✅ Segnato: hai schierato per la <b>Giornata {round_}</b>.\n"
        "Niente più promemoria per questa giornata, mister — si riattivano da soli alla prossima."
    )


def lineup_already_confirmed(round_: int) -> str:
    return (
        f"Avevi già segnato la <b>Giornata {round_}</b> come schierata, mister: "
        "i promemoria restano silenziati."
    )


def lineup_confirmation_cancelled(round_: int) -> str:
    return (
        f"↩️ Annullato: la <b>Giornata {round_}</b> non è più segnata come schierata, "
        "i promemoria residui riprendono."
    )


def lineup_not_confirmed() -> str:
    return "Non risultava nessuna conferma da annullare, mister."


def group_lineup_confirmed(round_: int, result: "GroupConfirmResult") -> str:
    """Feedback after one manager confirms in a group (ADR 0027)."""
    head = (
        f"Avevi già segnato la <b>Giornata {round_}</b>, mister"
        if result.already
        else f"✅ Segnato: hai schierato per la <b>Giornata {round_}</b>"
    )
    count = f"\nSiamo a <b>{result.confirmed}/{result.total}</b> nel gruppo."
    if result.complete:
        silenced = (
            f"{head}.{count}\n"
            "Hanno schierato tutti: niente più promemoria per questa giornata, "
            "si riattivano da soli alla prossima."
        )
        if result.roster_closed:
            return silenced
        # The lazy roster is exactly where "tutti" can mean "l'unico che ha cliccato".
        return (
            f"{silenced}\n"
            f"Le iscrizioni però sono ancora aperte: se manca qualcuno, con /iscrizioni "
            f"può registrarsi con <b>{keyboards.ACTION_ROSTER_JOIN}</b> e i promemoria "
            f"riprendono finché non ha schierato anche lui."
        )
    if not result.roster_closed:
        return (
            f"{head}.{count}\n"
            f"Le iscrizioni sono ancora aperte: con /iscrizioni chi manca può registrarsi "
            f"con <b>{keyboards.ACTION_ROSTER_JOIN}</b>, così il conteggio è quello vero."
        )
    return f"{head}.{count}\nI promemoria si fermano quando hanno schierato tutti."


def group_lineup_cancelled(round_: int, result: "GroupConfirmResult") -> str:
    return (
        f"↩️ Annullato: non risulti più schierato per la <b>Giornata {round_}</b>.\n"
        f"Siamo a <b>{result.confirmed}/{result.total}</b>, i promemoria del gruppo proseguono."
    )


def group_lineup_confirmed_toast(result: "GroupConfirmResult") -> str:
    """Short toast on the button press; the message keyboard carries the counter."""
    if result.complete:
        return f"Hanno schierato tutti ({result.confirmed}/{result.total}): promemoria fermi."
    if result.already:
        return f"Eri già segnato. Siamo a {result.confirmed}/{result.total}."
    return f"Segnato. Siamo a {result.confirmed}/{result.total}."


def group_lineup_cancelled_toast(result: "GroupConfirmResult") -> str:
    return f"Conferma annullata. Siamo a {result.confirmed}/{result.total}."


def roster_status(participants: int, *, closed: bool) -> str:
    if closed:
        return (
            f"<b>Iscrizioni chiuse.</b> "
            f"Manager registrati in questo gruppo: <b>{participants}</b>.\n"
            f"I promemoria di una giornata si fermano quando hanno schierato tutti.\n"
            f"Se la rosa è cambiata, un amministratore può usare "
            f"<b>{keyboards.ACTION_ROSTER_REOPEN}</b>: azzera l'elenco e riparte da capo."
        )
    return (
        f"<b>Iscrizioni aperte.</b> Manager registrati finora: <b>{participants}</b>.\n"
        f"Chi gioca in questo gruppo tocchi <b>{keyboards.ACTION_ROSTER_JOIN}</b>. "
        f"Quando ci siete tutti, un amministratore chiude con "
        f"<b>{keyboards.ACTION_ROSTER_CLOSE}</b>."
    )


def roster_group_only() -> str:
    return (
        "Le iscrizioni servono solo nei gruppi, mister: qui in privato "
        "/ho_schierato silenzia già i promemoria da solo."
    )


def roster_joined(participants: int) -> str:
    return f"Sei nell'elenco dei manager. Siamo in {participants}."


def roster_already_joined() -> str:
    return "Eri già nell'elenco dei manager, mister."


def roster_closed_toast() -> str:
    return "Le iscrizioni sono chiuse: un amministratore può riaprirle."


def lineup_group_use_command() -> str:
    """Defensive toast: a private-shaped lineup button pressed in a group (ADR 0027)."""
    return "Qui nel gruppo la conferma è per manager: usa /ho_schierato."


def group_lineup_nothing_to_cancel() -> str:
    return "Non risultava nessuna conferma tua da annullare, mister."


def unknown_command() -> str:
    return "Comando non riconosciuto. Usa /help per l'elenco dei comandi."


def _offsets_list(reminder_offsets: Sequence[timedelta]) -> str:
    """Bullet list, one reminder offset per line."""
    return "\n".join(f"• <b>{fmt.format_duration(offset)}</b>" for offset in reminder_offsets)


def subscription_enabled(reminder_offsets: Sequence[timedelta]) -> str:
    return (
        "✅ Promemoria attivati in questa chat, mister!\n"
        f"Arrivano prima di ogni scadenza:\n{_offsets_list(reminder_offsets)}"
    )


def subscription_already_enabled(reminder_offsets: Sequence[timedelta]) -> str:
    return (
        "Va già tutto bene: i promemoria sono già attivi in questa chat, arrivano "
        f"prima di ogni scadenza:\n{_offsets_list(reminder_offsets)}"
    )


def subscription_topic_bound() -> str:
    """Fragment appended to a subscribe/offsets confirmation (ADR 0025), not a standalone body."""
    return "\n📌 Li manderò solo in questo topic."


def subscription_topic_unbound() -> str:
    """Fragment appended to a subscribe/offsets confirmation (ADR 0025), not a standalone body."""
    return "\n📌 Torno a mandarli nella chat principale."


def subscription_destination(*, bound_here: bool, bound_elsewhere: bool) -> str:
    """Where reminders land, appended to subscription_status() in forums only (ADR 0031).

    Non-forum chats have no topics at all, so their status text stays untouched.
    The topic is never named: the Bot API can't resolve one (ADR 0025).
    """
    if bound_here:
        return "\n📌 Li mando in questo topic."
    if bound_elsewhere:
        return "\n📌 Li mando in un altro topic di questo gruppo."
    return "\n📌 Li mando nella chat principale."


def subscription_topic_unchanged() -> str:
    """Toast for a destination button pressed when nothing would move (ADR 0031)."""
    return "I promemoria arrivano già lì, mister."


def subscription_disabled() -> str:
    return "🔕 Promemoria disattivati in questa chat. Se ti penti, /promemoria ti aspetta 😏"


def subscription_not_enabled() -> str:
    return "I promemoria non sono ancora attivi in questa chat."


def subscription_status(reminder_offsets: Sequence[timedelta]) -> str:
    return (
        "🔔 Promemoria <b>attivi</b> in questa chat, arrivano "
        f"prima di ogni scadenza:\n{_offsets_list(reminder_offsets)}"
    )


def admin_only() -> str:
    return "Solo gli amministratori del gruppo possono attivare o disattivare i promemoria."


def offsets_usage(current: Sequence[timedelta] | None) -> str:
    status = (
        f"Attualmente sono attivi questi promemoria prima della scadenza:\n"
        f"{_offsets_list(current)}\n\n"
        if current
        else "I promemoria non sono ancora attivi in questa chat.\n\n"
    )
    return (
        f"{status}"
        "Scegli gli orari toccando le caselle qui sotto, poi premi "
        f"<b>{keyboards.ACTION_SAVE}</b>.\n"
        f"In alternativa usa <code>{OFFSETS_USAGE_EXAMPLE}</code> "
        "(unità m/h/g, tra 1 minuto e 7 giorni, massimo 10 orari), oppure "
        "<code>/personalizza_orari default</code> per tornare ai valori predefiniti."
    )


def offsets_custom_prompt() -> str:
    return (
        "✏️ <b>Rispondi a questo messaggio</b> con gli orari che vuoi impostare, ad esempio "
        f"<code>{OFFSETS_USAGE_EXAMPLE}</code> (unità m/h/g, tra 1 minuto e 7 giorni, "
        "massimo 10 orari).\n\n"
        f"Usa /annulla oppure il bottone ⬅️ {keyboards.ACTION_BACK} "
        "per tornare alle caselle predefinite "
        "senza cambiare nulla."
    )


def offsets_custom_cancelled() -> str:
    return "Nessun problema: annullato, gli orari restano quelli di prima."


def offsets_custom_timeout() -> str:
    return (
        "Tempo scaduto: gli orari restano quelli di prima. Usa /personalizza_orari per riprovare."
    )


def offsets_selection_empty() -> str:
    return "Serve almeno un orario prima di salvare, mister: tocca una casella."


def offsets_updated(reminder_offsets: Sequence[timedelta], *, newly_subscribed: bool) -> str:
    intro = (
        "✅ Promemoria attivati e orari impostati in questa chat, mister!\n"
        if newly_subscribed
        else "✅ Orari dei promemoria aggiornati!\n"
    )
    return f"{intro}Arrivano prima di ogni scadenza:\n{_offsets_list(reminder_offsets)}"


def offsets_reset(reminder_offsets: Sequence[timedelta]) -> str:
    return (
        "↩️ Orari dei promemoria ripristinati ai valori predefiniti.\n"
        f"Arrivano prima di ogni scadenza:\n{_offsets_list(reminder_offsets)}"
    )


def offsets_invalid_empty() -> str:
    return f"Serve almeno un orario, mister: prova con <code>{OFFSETS_USAGE_EXAMPLE}</code>."


def offsets_too_many(max_offsets: int) -> str:
    return f"Troppi orari, mister: al massimo {max_offsets}."


def offsets_invalid_token(token: str) -> str:
    return (
        f"'{html.escape(token)}' non è un orario valido, mister: usa un numero seguito da "
        "m, h oppure g, ad esempio <code>24h</code> o <code>2g</code>."
    )


def offsets_out_of_range(token: str, minimum: timedelta, maximum: timedelta) -> str:
    return (
        f"'{html.escape(token)}' è fuori portata, mister: ogni orario deve "
        f"stare tra <b>{fmt.format_duration(minimum)}</b> e "
        f"<b>{fmt.format_duration(maximum)}</b>."
    )
