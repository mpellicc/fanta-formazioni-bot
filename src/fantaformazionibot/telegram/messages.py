"""All user-facing texts (Italian, HTML parse mode). Dynamic values are pre-formatted strings."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from fantaformazionibot import format as fmt

CHANNEL_USERNAME = "@fantaformazionireminders"
MAINTAINER_USERNAME = "@pelliccm"


def start(reminder_offsets: Sequence[timedelta]) -> str:
    offsets = fmt.join_list([fmt.format_duration(offset) for offset in reminder_offsets])
    return (
        "Ciao! 👋 Sono <b>FantaFormazioni Bot</b>.\n\n"
        "Ti ricordo di schierare la formazione prima della scadenza "
        "di ogni giornata di Serie A.\n"
        f"I promemoria arrivano <b>{offsets}</b> prima della scadenza "
        f"sul canale {CHANNEL_USERNAME}: unisciti per non dimenticartene mai più!\n\n"
        "Usa /prossima_scadenza per sapere quanto tempo ti resta, "
        "oppure /help per l'elenco dei comandi."
    )


def help_() -> str:
    return (
        "Ecco cosa posso fare:\n"
        "• /prossima_scadenza — data e ora della prossima scadenza e tempo rimanente\n"
        "• /start — presentazione del bot\n"
        "• /help — questo messaggio\n\n"
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
