# ADR 0028 — Log a un evento per riga, con campi `chiave=valore`

**Stato**: accettata

## Contesto

Il bot in produzione emetteva ~9 righe di log in due ore di esecuzione, quasi tutte
di avvio. Le 13 chiamate di logging del sorgente vivevano in 3 soli file
(`reminders/jobs.py`, `telegram/errors.py`, `app.py`): nessun handler di comando o
callback lasciava traccia. Con 14 iscrizioni attive e traffico utente reale, dai log
era impossibile rispondere a "cosa è appena successo?" o "perché quell'utente si
lamenta?" senza aprire il DB.

Esiste inoltre un consumatore esterno: la dashboard `osservatorio-hq` espone
`docker logs -f --timestamps` del container via SSE e parsa ogni riga con una regex
costruita sul `format` di `basicConfig` in `app.py`.

## Decisione

1. **Si loggano gli eventi, non il traffico.** Una riga per ogni cambiamento di stato
   visibile all'utente o per ogni diniego di permesso. Nessuna riga per i poll di
   Telegram, per le letture (`/start`, `/prossima_scadenza`, `/stato_promemoria`) o
   per le query al DB.

2. **Un solo punto di emissione**: `telegram/events.py` espone `log_event(action,
   chat_id, outcome, **fields)`, che rende la riga
   `action=<slug> chat_id=<id> outcome=<slug> [chiave=valore ...]`.
   I valori devono essere token senza spazi (id, slug, numeri): mai prosa e **mai
   testo scritto dall'utente**, che romperebbe il parsing per chiave e finirebbe in
   chiaro nei log.

3. **Le chiamate stanno nelle funzioni core di `commands.py`**, non negli handler.
   `subscribe`, `unsubscribe`, `set_offsets`, `confirm_lineup`,
   `confirm_group_lineup` e le loro inverse sono già condivise fra comandi e
   callback: loggando lì, ogni percorso è coperto una volta sola e la riga descrive
   l'esito reale invece dell'intenzione.

4. **`outcome` distingue sempre il no-op.** ADR 0024 stabilisce che
   `/promemoria_on` è idempotente e che loggare ogni chiamata inventerebbe
   iscritti: `outcome=created` vs `outcome=noop` mantiene quella distinzione, quindi
   contare `outcome=created` resta un conteggio di iscrizioni vere.

5. **Il `format` di `basicConfig` è un contratto verso `osservatorio-hq`**
   (`src/components/LogViewer.tsx`, costante `LINE_RE`). Le chiavi stanno dentro
   `%(message)s`, quindi la dashboard continua a colorare e filtrare senza modifiche.
   Cambiare quel `format` richiede di aggiornare la regex nell'altro repo.

6. **`logging.captureWarnings(True)`**: i warning di libreria passano dal modulo
   `warnings` e bypassano il formato, producendo righe non parsabili. Vengono
   convogliati in `logging` (logger `py.warnings`). **Limite noto**: il
   `PTBUserWarning` di `callbacks.py` viene emesso a import-time, prima che
   `setup_logging` giri, quindi resta non parsato. Renderlo parsabile richiederebbe
   di configurare il logging prima di importare `app`, cioè spostare `setup_logging`
   fuori da `app.py`: non vale due righe di rumore all'avvio, e il viewer le mostra
   comunque grezze.

7. **Rotazione dei log del container**: `compose.yaml` fissa `max-size: 10m` e
   `max-file: 3`. Il driver `json-file` senza opzioni cresce senza limite, e su una VM
   Oracle free tier l'aumento di volume introdotto da questo ADR lo renderebbe un
   problema di disco.

## Conseguenze

- Una conversazione si ricostruisce filtrando `chat_id=<id>` nella dashboard.
- Repository, planner e provider del calendario restano senza logging: il valore per
  la dashboard è basso e il rischio di rumore alto. Se servirà, sarà un ADR separato.
- Il livello resta `INFO` per gli eventi; gli errori continuano a passare da
  `telegram/errors.py` e da `reminders/jobs.py` come prima.
- Il vocabolario delle chiavi (`action`, `chat_id`, `outcome`, `round`, `user_id`,
  `chat_type`, `thread_id`, `offsets`, `reason`) va esteso, non reinventato: un nome
  nuovo per un concetto esistente rompe i filtri già salvati.
