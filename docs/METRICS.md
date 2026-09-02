# Metriche — cosa `osservatorio-hq` può leggere

Contratto verso il consumatore esterno. Vedi ADR 0029 per il perché, ADR 0022
e 0024 per le due tabelle preesistenti.

## 1. Schema

Nuova tabella, append-only. Nessuna tabella o colonna esistente è stata
modificata.

```sql
CREATE TABLE bot_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT    NOT NULL,   -- ISO 8601 UTC tz-aware ("2026-09-02T13:04:50.306983+00:00")
    action      TEXT    NOT NULL,   -- cosa è successo
    outcome     TEXT    NOT NULL,   -- com'è andata
    chat_id     INTEGER,            -- NULL per gli eventi di processo (startup, calendario)
    chat_type   TEXT,               -- 'private' | 'group' | 'supergroup' | 'channel', NULL se ignoto
    user_id     INTEGER,            -- l'utente che ha agito, dove ha senso
    round       INTEGER,            -- la giornata, dove ha senso
    detail      TEXT                -- JSON degli altri campi, o NULL
);
CREATE INDEX bot_events_time_idx   ON bot_events (occurred_at);
CREATE INDEX bot_events_action_idx ON bot_events (action, occurred_at);
CREATE INDEX bot_events_chat_idx   ON bot_events (chat_id, occurred_at);
```

**Cosa significa una riga**: un fatto accaduto, in un istante, con il suo
esito. Mai un'intenzione, mai un poll di Telegram, mai una lettura di DB. Le
righe non vengono mai aggiornate né cancellate.

`chat_type` è denormalizzato di proposito: un `JOIN subscriptions` perderebbe
esattamente le chat che interessa contare, quelle uscite.

### Vocabolario

Aggiungere un `action` è sicuro; **rinominarne o riusarne uno è breaking**.

| `action` | `outcome` | colonne popolate | campi in `detail` |
|---|---|---|---|
| `subscribe` | `created`, `noop` | `chat_type` | `thread_id`, `topic_changed` |
| `unsubscribe` | `deleted`, `noop` | `chat_type` | — |
| `set_offsets` | `created`, `updated` | `chat_type` | `offsets` (secondi, csv), `thread_id`, `topic_changed` |
| `lineup_confirm` | `confirmed`, `noop` | `round` | — |
| `lineup_undo` | `undone`, `noop` | `round` | — |
| `group_lineup_confirm` | `confirmed`, `noop` | `round`, `user_id` | `confirmed`, `total`, `complete` |
| `group_lineup_undo` | `undone`, `noop` | `round`, `user_id` | `confirmed`, `total` |
| `roster_join` | `joined`, `noop`, `closed` | `user_id` | — |
| `roster_close` | `closed` | — | — |
| `roster_reset` | `reopened` | — | — |
| `permission_check` | `denied` | `user_id` | `reason` (`not_admin`, `no_sender`) |
| `reminder_send` | `sent`, `failed` | `chat_type`, `round` | `offset_seconds`, `error_kind` (`dead_chat`, `other`) |
| `calendar_refresh` | `ok`, `failed` | — (`chat_id` NULL) | `matchdays` |
| `calendar_stale` | `detected` | `round` (`chat_id` NULL) | — |
| `startup` | `ok` | — (`chat_id` NULL) | — |

`outcome` distingue sempre il no-op: contare `outcome='created'` resta un
conteggio di iscrizioni vere, non di comandi digitati (ADR 0024).

## 2. Metriche ora calcolabili

Query verificate su un DB reale.

**Consegna nel tempo**
```sql
SELECT strftime('%Y-%W', occurred_at) AS week, outcome,
       COUNT(*) AS n, COUNT(DISTINCT chat_id) AS chats
FROM bot_events WHERE action = 'reminder_send'
GROUP BY week, outcome ORDER BY week;
```

**Tasso di consegna**
```sql
SELECT 1.0 * SUM(outcome = 'sent') / COUNT(*) AS delivery_rate
FROM bot_events WHERE action = 'reminder_send';
```

**Errori per tipo**
```sql
SELECT json_extract(detail, '$.error_kind') AS kind, COUNT(*) AS n
FROM bot_events WHERE action = 'reminder_send' AND outcome = 'failed'
GROUP BY kind;
```

**Efficacia — conferme contro reminder, per giornata**
```sql
SELECT round,
  COUNT(DISTINCT CASE WHEN action='reminder_send' AND outcome='sent'      THEN chat_id END) AS reminded,
  COUNT(DISTINCT CASE WHEN action='lineup_confirm' AND outcome='confirmed' THEN chat_id END) AS confirmed
FROM bot_events WHERE round IS NOT NULL GROUP BY round;
```

**Margine sulla deadline** — differenza fra `occurred_at` della conferma e
`matchdays.kickoff_utc` meno il `DEADLINE_MARGIN` di configurazione (il
margine non è in DB: è una env var, va passata alla query).

**Uso delle azioni, per tipo di chat**
```sql
SELECT action, chat_type, COUNT(*) FROM bot_events
WHERE chat_id IS NOT NULL GROUP BY action, chat_type;
```

**Personalizzazione — stato attuale e storia**
```sql
SELECT reminder_offsets, COUNT(*) FROM subscriptions GROUP BY reminder_offsets;  -- già possibile prima
SELECT occurred_at, chat_id, json_extract(detail,'$.offsets') FROM bot_events
WHERE action = 'set_offsets' ORDER BY occurred_at;                               -- nuovo: la storia
```

**Salute**
```sql
SELECT date(occurred_at) AS day, outcome, COUNT(*) FROM bot_events
WHERE action = 'calendar_refresh' GROUP BY day, outcome;
SELECT occurred_at FROM bot_events WHERE action = 'startup' ORDER BY id DESC;  -- riavvii
SELECT MAX(occurred_at) FROM bot_events;  -- staleness: il bot è vivo?
```

## 3. Cosa resta non calcolabile

- **Quante persone hanno *letto* un reminder.** L'API Bot non espone letture né
  visualizzazioni di canale. `outcome='sent'` significa "Telegram l'ha
  accettato", non "qualcuno l'ha visto". Nessuno schema può cambiarlo.
- **I comandi di sola lettura** (`/start`, `/prossima_scadenza`,
  `/stato_promemoria`, `/aiuto`): non registrati, per decisione confermata
  (ADR 0028 §1, ADR 0029 §5). Le metriche d'uso coprono le azioni, non le
  consultazioni.
- **Tutto ciò che è accaduto prima del deploy**: reminder, conferme e comandi
  dei round passati restano senza data, per sempre. Ogni serie temporale parte
  dal primo evento registrato. Nessun backfill (ADR 0022).
- **`chat_type` su `lineup_confirm`/`lineup_undo`/`roster_*`**: le funzioni core
  ricevono solo `chat_id`, quindi la colonna è `NULL` su quelle righe. Si
  recupera prendendo un `chat_type` non nullo di quella chat
  (`SELECT chat_type FROM bot_events WHERE chat_id = ? AND chat_type IS NOT NULL
  ORDER BY id DESC LIMIT 1`), che sopravvive anche se la chat esce.
- **Chi ha bloccato il bot senza che un reminder fosse dovuto**: resta "attivo"
  finché non ne scatta uno (limite già noto da ADR 0024).
- **Chi c'è dietro una chat privata** (nome, lega, squadra): non lo
  raccogliamo, e non è previsto iniziare.

## 4. Deploy

**Nessun passo manuale.** La migrazione è solo `CREATE TABLE/INDEX IF NOT
EXISTS` dentro `_create_tables`, che gira a ogni avvio: nessun `ALTER`, nessuna
riscrittura, nessun backfill. Su un DB preesistente la tabella nasce vuota e si
popola dal primo evento. La lettura in `mode=ro` durante l'esecuzione resta
sicura come prima (WAL invariato).
