from enum import StrEnum

import emoji


class Messages(StrEnum):
    START = """Grazie per avermi avviato\\!\n
Ti notificherò quando l'inserimento della formazione starà per scadere\\.
La notifica sarà un giorno, un'ora e cinque minuti prima della scadenza \\(impostata a 5 minuti dall'inizio della giornata\\)\\.\n
Al momento, funziono all'interno del canale @fantaformazionireminders\\. Unisciti al canale per ricevere le notifiche\\!\n
Invia /help per ulteriori informazioni\\."""
    HELP = """Ecco la lista dei comandi:
\\- /start: Avvia il bot\\.
\\- /help: Questo messaggio\\.
\\- /prossima\\_scadenza: Invierò un messaggio che indica quando comincia la prossima giornata e quanto tempo hai ancora per inserire la formazione\\.\n
Se hai bisogno di ulteriori informazioni o aiuto, scrivi a @pelliccm\\."""
    NEXT_MATCH = emoji.emojize("""La prossima giornata comincerà il \n__{match_date} alle {match_time}__\\.\n
Hai ancora *{deadline_str}* per inserire la formazione :alarm_clock:""")
    NEXT_MATCH_NOT_FOUND = emoji.emojize(
        "Non ci sono altre partite per questa stagione\\! :partying_face:"
    )
    LINEUP_NOTIFICATION = emoji.emojize(""":police_car_light: Ricordati di inserire la formazione :police_car_light:\n
Hai ancora *{deadline_str}*\\!""")
    NOT_IMPLEMENTED = "Questo comando non è stato ancora implementato\\."
