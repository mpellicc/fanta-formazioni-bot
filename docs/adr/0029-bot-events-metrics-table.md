# ADR 0029 — `bot_events`: gli eventi di ADR 0028 anche in SQLite

- Status: accepted
- Date: 2026-09-02

## Contesto

`osservatorio-hq` (ADR 0022) legge il DB di produzione in sola lettura, via SSH
e `docker exec`, con un guard che rifiuta qualunque istruzione diversa da
`SELECT`. Nessun ETL, nessuna cache, nessun accesso ai log applicativi.
Conseguenza: **una metrica esiste solo se è una riga in SQLite.**

Con lo schema attuale tre domande non sono esprimibili:

1. **Quando è partito un reminder.** `sent_reminders` è una tabella di
   deduplicazione (`chat_id, round, offset_seconds`), senza tempo e mai
   ripulita fra i round. Produce solo un totale storico monotono: oggi 16 chat
   "raggiunte" contro 14 iscritte, perché include due chat che nel frattempo
   sono uscite. Nessuna serie temporale, né settimanale né per giornata.
2. **Se un invio è fallito.** Un rifiuto di Telegram non lascia traccia in DB:
   `_prune_dead_chat` cancella l'iscrizione e logga, e basta. Tasso di consegna
   e latenza di `dead_chat` sono non calcolabili.
3. **Quando una formazione è stata confermata.** `lineup_confirmations` e
   `group_lineup_confirmations` sono `(chat_id, round[, user_id])` senza
   timestamp: si sa *che* qualcuno ha confermato, mai *quando*. In più
   `reopen_roster` (ADR 0027) le cancella, quindi la storia sparisce.

ADR 0028 ha però già fatto il lavoro di modellazione: ha deciso quali fatti
sono eventi di dominio, come si chiamano (`action`/`chat_id`/`outcome` + campi)
e dove si emettono — un unico punto, `telegram/events.py::log_event`, chiamato
dalle funzioni core condivise fra comandi e callback. Quel lavoro oggi produce
righe di testo effimere in `docker logs`, ruotate a 10 MB × 3.

## Decisione

**Una sola tabella append-only, `bot_events`, che rispecchia il vocabolario di
ADR 0028 ed è scritta dallo stesso punto di emissione.** Un fatto nuovo è un
`action` nuovo, non una migrazione.

```sql
CREATE TABLE IF NOT EXISTS bot_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT    NOT NULL,   -- ISO 8601 UTC, tz-aware
    action      TEXT    NOT NULL,
    outcome     TEXT    NOT NULL,
    chat_id     INTEGER,            -- NULL per gli eventi di processo
    chat_type   TEXT,
    user_id     INTEGER,
    round       INTEGER,
    detail      TEXT                -- JSON degli altri campi, o NULL
);
```

Indici su `(occurred_at)`, `(action, occurred_at)`, `(chat_id, occurred_at)`:
sono le tre direzioni in cui l'osservatorio filtra.

**Semantica di una riga: un fatto accaduto, in un istante, con il suo esito.**
Mai un'intenzione, mai un poll, mai una lettura di DB.

1. **`log_event` diventa a due destinazioni.** Guadagna un parametro
   keyword-only `repository`; quando è presente, scrive anche la riga. Il
   formato della riga di log non cambia, quindi la regex di `LogViewer.tsx`
   resta valida (ADR 0028 §5). Resta un unico punto di emissione: log e DB non
   possono divergere.

2. **`chat_type`, `user_id` e `round` sono colonne, non JSON.** Sono i tre assi
   su cui si aggrega; il resto dei campi (`offsets`, `reason`, `thread_id`,
   `topic_changed`, `error_kind`…) finisce in `detail` come JSON, dove
   `json_extract` basta e avanza per i volumi in gioco.

3. **`chat_type` è denormalizzato di proposito.** `sent_reminders` ha 16 chat
   contro 14 iscritte: un `JOIN subscriptions` perderebbe esattamente le chat
   che interessa contare, quelle uscite. È la stessa ragione per cui ADR 0024
   lo tiene dentro `subscription_events`.

4. **Nuovi punti di scrittura oltre a quelli di ADR 0028**:
   - `reminders/jobs.py::send_reminder_job` — `action=reminder_send` con
     `outcome=sent` dopo `mark_reminder_sent`, e `outcome=failed` con
     `detail.error_kind` (`dead_chat` | `other`) nel ramo di eccezione, che
     oggi prunifica in silenzio o rilancia.
   - `refresh_calendar` — `action=calendar_refresh`, `outcome=ok|failed`.
   - `_alert_if_stale` — `action=calendar_stale`, `outcome=detected`.
   - `app.py::_post_init` — `action=startup`, `outcome=ok`.
   Gli eventi di processo non hanno chat: `chat_id` è `NULL` e per loro non si
   passa da `log_event` (il cui prefisso `chat_id=` è un contratto verso la
   dashboard) ma da `record_process_event`, che scrive solo in DB e lascia
   intatte le `logger.info` già esistenti.

5. **Si registrano solo le scritture.** ADR 0028 §1 esclude i comandi di sola
   lettura (`/start`, `/prossima_scadenza`, `/stato_promemoria`, `/aiuto`) e
   quella decisione **resta valida anche per il DB**: si misurano i
   cambiamenti di stato, non il traffico. Le metriche sull'uso dei comandi
   coprono quindi le sole azioni, non le consultazioni.

6. **`subscription_events` resta invariata.** È già un contratto consumato
   dall'osservatorio (ADR 0024); replicarne il contenuto in `bot_events`
   creerebbe due fonti che possono divergere sullo stesso fatto. `bot_events`
   copre ciò che oggi non ha nessuna tabella. Dove entrambe descrivono
   un'iscrizione, `subscription_events` resta la fonte per lo stato,
   `bot_events` per l'azione che l'ha prodotta.

7. **`sent_reminders` resta invariata.** Continua a essere la chiave di dedup
   che il bot interroga a ogni invio; il tempo vive in `bot_events`.

8. **Nessun backfill.** Come in ADR 0022 e 0024: ogni serie temporale parte dal
   deploy. I round, i comandi e le conferme già avvenuti restano senza data,
   per sempre e di proposito.

## Alternative considerate

- **`ALTER TABLE sent_reminders ADD COLUMN sent_at`**: la mossa più economica,
  ma copre metà del problema — nessun fallimento, quindi nessun tasso di
  consegna — e trasforma in log una tabella che ha un ruolo funzionale nel
  percorso di invio. Scartata.
- **Una tabella per concern** (`reminder_deliveries`, `command_usage`,
  `health_checks`): schema più esplicito, ma ogni fatto nuovo diventa una
  migrazione e tre tabelle condividerebbero comunque le stesse quattro colonne.
  Scartata.
- **Timestamp sulle tabelle di stato** (`lineup_confirmations.confirmed_at`):
  non sopravvive a `reopen_roster`, che le cancella, e non registra gli annulli.
  Le metriche non vanno derivate dalle tabelle di stato. Scartata.
- **Una riga per update Telegram ricevuto**: rumore proporzionale al traffico
  invece che agli eventi di dominio, e non risponde a nessuna domanda che le
  righe sopra non coprano già. Scartata.
- **Snapshot giornalieri dei conteggi**: ridondante con `subscription_events` +
  `created_at`, e congelerebbe un errore di conteggio invece di lasciarlo
  correggere a posteriori. Scartata.
- **Log strutturati esportati (JSON lines) invece del DB**: l'osservatorio non
  ha ETL e legge solo SQL. Fuori dai vincoli. Scartata.

## Conseguenze

- `bot_events` è la terza tabella che `osservatorio-hq` legge direttamente:
  nomi di colonna e valori di `action`/`outcome` diventano un contratto
  esterno, con la stessa avvertenza di ADR 0022 e 0024 — nulla in questo repo
  lo fa rispettare. **Aggiungere un `action` è sicuro; rinominarne o
  riusarne uno è breaking.**
- Il vocabolario di ADR 0028 §7 vale ora anche per le colonne: un nome nuovo
  per un concetto esistente rompe sia i filtri della dashboard sia le query.
- La tabella cresce con gli eventi di dominio: stimate ~4.000 righe a stagione
  con 14 iscritti (~3.200 invii, il resto azioni e salute). Nessuna retention
  per ora; vale la nota di ADR 0024 — se servirà, aggregare prima di potare.
- La migrazione è solo `CREATE TABLE/INDEX IF NOT EXISTS` nel blocco già
  esistente di `repository.py`: nessun `ALTER`, nessuna riscrittura, **nessun
  passo manuale al deploy**. Su un DB preesistente la tabella nasce vuota e si
  popola dal primo evento.
- Un fallimento di scrittura su `bot_events` non deve impedire un invio o un
  comando: la metrica è secondaria rispetto alla funzione, quindi la scrittura
  è isolata in `events.py` e un'eccezione viene loggata, non propagata.
