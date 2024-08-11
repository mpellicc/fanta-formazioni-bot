from enum import StrEnum


class Messages(StrEnum):
    START = """Grazie per avermi avviato\\!\n
Ti notificherò quando l'inserimento della formazione starà per scadere\\.
La notifica sarà un giorno, un'ora e dieci minuti prima della scadenza \\(impostata a 5 minuti dall'inizio della giornata\\)\\.\n
Invia /help per ulteriori informazioni\\."""
    HELP = """Ecco la lista dei comandi:
\\- /start: Avvia il bot\\.
\\- /help: Questo messaggio\\.
\\- /aggiungi\\_data: Inizio una conversazione per aggiungere una data al calendario da notificare\\. Capirò in automatico la chat da cui il comando proviene e ti avviserò lì\\.
Puoi anche inviare il comando seguito da una data formattata in questo modo `dd/MM/yyyy,HH:mm`\\.
\\- /prossima\\_scadenza: Invierò un messaggio che indica quando scade la prossima formazione da inserire\\.
\\- /annulla: Permette di uscire da una conversazione con il bot\\.\n
Se hai bisogno di ulteriori informazioni o aiuto, scrivi a @pelliccm\\."""
