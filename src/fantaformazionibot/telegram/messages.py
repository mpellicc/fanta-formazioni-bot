"""All user-facing texts (Italian, HTML parse mode). Dynamic values are pre-formatted strings."""

import html
from collections.abc import Sequence
from datetime import datetime, timedelta

from fantaformazionibot import format as fmt

OFFSETS_USAGE_EXAMPLE = "/personalizza_orari 24h 1h 5m"

CHANNEL_USERNAME = "@fantaformazionireminders"
MAINTAINER_USERNAME = "@pelliccm"


def start(reminder_offsets: Sequence[timedelta]) -> str:
    offsets = fmt.join_list([fmt.format_duration(offset) for offset in reminder_offsets])
    return (
        "Ciao! 👋 Sono <b>FantaFormazioni Bot</b>.\n\n"
        "Ti ricordo di schierare la formazione prima della scadenza "
        "di ogni giornata di Serie A.\n"
        f"I promemoria arrivano <b>{offsets}</b> prima della scadenza "
        f"sul canale {CHANNEL_USERNAME}: unisciti per non dimenticartene mai più!\n"
        "Oppure usa /promemoria_on per riceverli direttamente qui, "
        "in questa chat o in un gruppo.\n\n"
        "Usa /prossima_scadenza per sapere quanto tempo ti resta, "
        "oppure /help per l'elenco dei comandi."
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
        f"Hai ancora <b>{fmt.format_remaining(deadline, now)}</b> per schierare la formazione."
    )


def no_upcoming_deadline() -> str:
    return "Non ci sono altre giornate in calendario per questa stagione! 🥳"


def reminder(round_: int, deadline: datetime, now: datetime) -> str:
    return (
        "🚨 <b>Ricordati di schierare la formazione!</b> 🚨\n\n"
        f"📅 Giornata {round_} — scadenza <b>{fmt.format_date(deadline)} "
        f"alle {fmt.format_time(deadline)}</b>.\n"
        f"Hai ancora <b>{fmt.format_remaining(deadline, now)}</b>!"
    )


def unknown_command() -> str:
    return "Comando non riconosciuto. Usa /help per l'elenco dei comandi."


def _offsets_line(reminder_offsets: Sequence[timedelta]) -> str:
    return fmt.join_list([fmt.format_duration(offset) for offset in reminder_offsets])


def subscription_enabled(reminder_offsets: Sequence[timedelta]) -> str:
    return (
        "✅ Promemoria attivati in questa chat!\n"
        f"Ti scriverò <b>{_offsets_line(reminder_offsets)}</b> prima di ogni scadenza.\n\n"
        "Usa /promemoria_off per disattivarli."
    )


def subscription_already_enabled(reminder_offsets: Sequence[timedelta]) -> str:
    return (
        "I promemoria sono già attivi in questa chat: arrivano "
        f"<b>{_offsets_line(reminder_offsets)}</b> prima di ogni scadenza."
    )


def subscription_disabled() -> str:
    return "🔕 Promemoria disattivati in questa chat. Usa /promemoria_on per riattivarli."


def subscription_not_enabled() -> str:
    return "I promemoria non sono attivi in questa chat. Usa /promemoria_on per attivarli."


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
    return "Operazione annullata: gli orari non sono cambiati."


def offsets_custom_timeout() -> str:
    return "Tempo scaduto: gli orari non sono cambiati. Usa /personalizza_orari per riprovare."


def offsets_selection_empty() -> str:
    return "Seleziona almeno un orario prima di salvare."


def offsets_updated(reminder_offsets: Sequence[timedelta], *, newly_subscribed: bool) -> str:
    intro = (
        "✅ Promemoria attivati e orari impostati in questa chat!\n"
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
    return f"Devi indicare almeno un orario, ad esempio <code>{OFFSETS_USAGE_EXAMPLE}</code>."


def offsets_too_many(max_offsets: int) -> str:
    return f"Puoi impostare al massimo {max_offsets} orari."


def offsets_invalid_token(token: str) -> str:
    return (
        f"'{html.escape(token)}' non è un orario valido. Usa un numero seguito da "
        "m, h oppure g, ad esempio <code>24h</code> o <code>2g</code>."
    )


def offsets_out_of_range(token: str, minimum: timedelta, maximum: timedelta) -> str:
    return (
        f"'{html.escape(token)}' non è nell'intervallo consentito: ogni orario deve "
        f"essere tra <b>{fmt.format_duration(minimum)}</b> e "
        f"<b>{fmt.format_duration(maximum)}</b>."
    )
