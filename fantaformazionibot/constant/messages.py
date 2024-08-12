from enum import StrEnum


class Messages(StrEnum):
    START = """Grazie per avermi avviato\\!\n
Ti notificherò quando l'inserimento della formazione starà per scadere\\.
La notifica sarà un giorno, un'ora e cinque minuti prima della scadenza \\(impostata a 5 minuti dall'inizio della giornata\\)\\.\n
Al momento, funziono all'interno del canale @fantaformazionireminders\\. Unisciti al canale per ricevere le notifiche!\\.\n
Invia /help per ulteriori informazioni\\."""
    HELP = """Ecco la lista dei comandi:
\\- /start: Avvia il bot\\.
\\- /help: Questo messaggio\\.
\\- /prossima\\_scadenza: Invierò un messaggio che indica quando scade la prossima formazione da inserire\\.\n
Se hai bisogno di ulteriori informazioni o aiuto, scrivi a @pelliccm\\."""
    NOT_IMPLEMENTED = """Questo comando non è stato ancora implementato\\."""
