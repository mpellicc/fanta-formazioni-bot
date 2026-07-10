"""All user-facing texts (Italian, HTML parse mode). Dynamic values are pre-formatted strings.

Voice & tone: ADR 0018 (goliardico-fantacalcistico, medium intensity, clean).
"""

import html
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from fantaformazionibot import format as fmt

OFFSETS_USAGE_EXAMPLE = "/personalizza_orari 24h 1h 5m"

CHANNEL_USERNAME = "@fantaformazionireminders"
MAINTAINER_USERNAME = "@pelliccm"

URGENT_REMINDER_THRESHOLD = timedelta(minutes=10)


def start(reminder_offsets: Sequence[timedelta]) -> str:
    offsets = fmt.join_list([fmt.format_duration(offset) for offset in reminder_offsets])
    return (
        "Ciao, mister! ⚽ Sono <b>FantaFormazioni Bot</b>.\n\n"
        "Ti tengo d'occhio le scadenze di ogni giornata di Serie A, così non "
        "schieri più mezza squadra in panchina.\n"
        f"I promemoria arrivano <b>{offsets}</b> prima della scadenza "
        f"sul canale {CHANNEL_USERNAME}: unisciti per non perderti niente!\n"
        "Oppure usa /promemoria_on per riceverli qui, in privato o in un gruppo.\n\n"
        "Usa /prossima_scadenza per sapere quanto tempo ti resta, "
        "oppure /help per l'elenco dei comandi."
    )


def help_() -> str:
    return (
        "Ecco il regolamento, mister:\n"
        "• /prossima_scadenza — data e ora della prossima scadenza e tempo rimanente\n"
        "• /promemoria_on — attiva i promemoria in questa chat\n"
        "• /promemoria_off — disattiva i promemoria in questa chat\n"
        "• /promemoria — stato dei promemoria in questa chat, "
        "con bottone per attivarli/disattivarli\n"
        "• /personalizza_orari — scegli gli orari dei promemoria da una tastiera di caselle, "
        "oppure passa direttamente gli orari come argomenti\n"
        "• /start — presentazione del bot\n"
        "• /help — questo messaggio\n\n"
        "Nella tastiera di /personalizza_orari, il bottone <b>Personalizzati</b> ti fa scegliere "
        "un orario non in lista: rispondi al messaggio che ti invio con un formato come "
        "<code>2g,12h,10m</code> (unità m/h/g).\n\n"
        "Nei gruppi, /promemoria_on, /promemoria_off e /personalizza_orari "
        "sono riservati agli amministratori (anche i bottoni corrispondenti).\n\n"
        f"Per segnalazioni o suggerimenti scrivi a {MAINTAINER_USERNAME}."
    )


def next_deadline(round_: int, deadline: datetime, now: datetime) -> str:
    return (
        f"📅 <b>Giornata {round_}</b>\n"
        f"⏰ Scadenza formazioni: <b>{fmt.format_date(deadline)} "
        f"alle {fmt.format_time(deadline)}</b>\n\n"
        f"Hai ancora <b>{fmt.format_remaining(deadline, now)}</b> per schierare la formazione ⚽"
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


def reminder(round_: int, deadline: datetime, now: datetime, offset_seconds: int) -> str:
    """Early reminders (offset > 10 min) rotate through a pool of variants; the last-call
    reminders (offset <= 10 min) always use the same fixed, urgent template (ADR 0018 §9)."""
    time = fmt.format_time(deadline)
    remaining = fmt.format_remaining(deadline, now)
    if offset_seconds <= URGENT_REMINDER_THRESHOLD.total_seconds():
        return _reminder_urgent(round_, time, remaining)
    date = fmt.format_date(deadline)
    variant = _REMINDER_POOL[_reminder_pool_index(round_, offset_seconds)]
    return variant(round_, date, time, remaining)


def unknown_command() -> str:
    return "Comando non riconosciuto. Usa /help per l'elenco dei comandi."


def _offsets_line(reminder_offsets: Sequence[timedelta]) -> str:
    return fmt.join_list([fmt.format_duration(offset) for offset in reminder_offsets])


def subscription_enabled(reminder_offsets: Sequence[timedelta]) -> str:
    return (
        "✅ Promemoria attivati in questa chat, mister!\n"
        f"Ti scriverò <b>{_offsets_line(reminder_offsets)}</b> prima di ogni scadenza.\n\n"
        "Usa /promemoria_off per disattivarli."
    )


def subscription_already_enabled(reminder_offsets: Sequence[timedelta]) -> str:
    return (
        "Va già tutto bene: i promemoria sono già attivi in questa chat, arrivano "
        f"<b>{_offsets_line(reminder_offsets)}</b> prima di ogni scadenza."
    )


def subscription_disabled() -> str:
    return "🔕 Promemoria disattivati in questa chat. Se ti penti, /promemoria_on ti aspetta 😏"


def subscription_not_enabled() -> str:
    return "I promemoria non sono ancora attivi in questa chat: usa /promemoria_on per svegliarli."


def subscription_status(reminder_offsets: Sequence[timedelta]) -> str:
    return (
        "🔔 Promemoria <b>attivi</b> in questa chat: arrivano "
        f"<b>{_offsets_line(reminder_offsets)}</b> prima di ogni scadenza.\n\n"
        "Usa /promemoria_off per disattivarli."
    )


def admin_only() -> str:
    return "Solo gli amministratori del gruppo possono attivare o disattivare i promemoria."


def offsets_usage(current: Sequence[timedelta] | None) -> str:
    status = (
        f"Attualmente arrivano <b>{_offsets_line(current)}</b> prima di ogni scadenza.\n\n"
        if current
        else "I promemoria non sono ancora attivi in questa chat.\n\n"
    )
    return (
        f"{status}"
        "Scegli gli orari toccando le caselle qui sotto, poi premi <b>Salva</b>.\n"
        f"In alternativa usa <code>{OFFSETS_USAGE_EXAMPLE}</code> "
        "(unità m/h/g, tra 1 minuto e 7 giorni, massimo 10 orari), oppure "
        "<code>/personalizza_orari default</code> per tornare ai valori predefiniti."
    )


def offsets_custom_prompt() -> str:
    return (
        "✏️ <b>Rispondi a questo messaggio</b> con gli orari che vuoi impostare, ad esempio "
        f"<code>{OFFSETS_USAGE_EXAMPLE}</code> (unità m/h/g, tra 1 minuto e 7 giorni, "
        "massimo 10 orari).\n\n"
        "Usa /annulla oppure il bottone ⬅️ Indietro per tornare alle caselle predefinite "
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
    return f"{intro}Ti scriverò <b>{_offsets_line(reminder_offsets)}</b> prima di ogni scadenza."


def offsets_reset(reminder_offsets: Sequence[timedelta]) -> str:
    return (
        "↩️ Orari dei promemoria ripristinati ai valori predefiniti.\n"
        f"Ti scriverò <b>{_offsets_line(reminder_offsets)}</b> prima di ogni scadenza."
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
