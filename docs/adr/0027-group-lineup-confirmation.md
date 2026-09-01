# ADR 0027: "Ho schierato" nei gruppi — roster lazy per-utente

- Status: accepted
- Date: 2026-09-01

## Context

ADR 0021 ha reso `/ho_schierato` disponibile **solo in chat privata**, per un problema
di correttezza emerso in fase di design: `subscriptions` è chiavata per `chat_id`, non
per utente (ADR 0008), quindi un gruppo è condiviso da più manager distinti e una
singola conferma silenzierebbe i promemoria di tutti gli altri. La variante gruppi è
stata rimandata a un ADR proprio; `docs/HANDOFF.md` ne conserva il design parziale: un
bivio chiuso il 2026-07-14 (iscrizione al roster tramite **bottone di
auto-registrazione**, non `@username` digitati — Telegram non garantisce la risoluzione
di uno username in `user_id` per chi non ha mai interagito col bot, e non tutti hanno
uno username pubblico) e quattro bivi lasciati aperti, chiusi con Matteo nella sessione
che precede questa ADR.

Il vincolo di fondo non è rimovibile: **il Bot API non enumera i membri non-admin di un
gruppo**. Non esiste modo di sapere chi sono "tutti i manager" della chat. L'unica
struttura costruibile è un roster *lazy*, popolato da chi si registra o da chi conferma.

## Decision

### 1. Roster lazy, con chiusura esplicita opzionale

Nuovo comando `/iscrizioni` (in gruppo): mostra lo stato del roster e i bottoni
"Sono un manager" (auto-registrazione, un tap) e "Chiudi iscrizioni"/"Riapri iscrizioni".

Il silenziamento scatta quando **tutti i partecipanti noti** hanno confermato per quella
giornata, **indipendentemente dal fatto che le iscrizioni siano state chiuse**. Chiudere
le iscrizioni non è un prerequisito: è ciò che rende preciso il significato di "tutti".
Scartata l'alternativa "nessun silenziamento finché un admin non chiude le iscrizioni":
un gruppo che non fa il setup non otterrebbe mai il beneficio della feature, e il
percorso zero-setup è quello che copre la maggioranza dei gruppi reali.

### 2. Permessi

**Chiunque** può premere "Ho schierato" e "Sono un manager": sono autodichiarazioni
personali, non azioni che riconfigurano la chat. **Solo gli admin** possono chiudere,
riaprire e resettare il roster. Coerente con ADR 0012, che gate esclusivamente le azioni
con effetto su *tutta* la chat (subscribe/unsubscribe/offset).

### 3. UI del conteggio

Il conteggio vive **nella label del bottone sul messaggio di promemoria**
(`✅ Ho schierato (3/5)`), aggiornata in place a ogni tap. Nessun messaggio di stato
separato: raddoppierebbe il rumore nel gruppo e richiederebbe una `send_message`
esplicita con `message_thread_id` (ADR 0025). Sui tap quasi simultanei l'ultimo edit
vince, ed è comunque corretto perché il conteggio viene **riletto dal DB dopo la
scrittura**, non incrementato dal valore mostrato; il `contextlib.suppress(BadRequest)`
già presente in `callbacks.py::_edit_markup` assorbe gli edit no-op.

### 4. Ciclo di vita del roster

Nessun `ChatMemberHandler` (plumbing oggi inesistente nel progetto). Chi lascia il gruppo
o smette di giocare si gestisce con la **riapertura del roster da parte di un admin**, che
svuota partecipanti e conferme e rimette le iscrizioni in stato aperto: copre con un solo
meccanismo sia il cambio lega a inizio stagione sia il manager che sparisce. Un
`ChatMemberHandler` non coprirebbe comunque il caso più frequente — chi resta nel gruppo
ma smette di giocare.

### 5. Storage

`lineup_confirmations (chat_id, round)` **resta invariata** e diventa il **flag di
silenziamento derivato** anche per i gruppi: quando l'ultimo partecipante conferma, si
inserisce la riga per-chat; se qualcuno annulla, la si rimuove. Conseguenza voluta:
`reminders/jobs.py` non cambia nella logica di skip — `reschedule_reminders` e
`send_reminder_job` continuano a leggere `is_lineup_confirmed(chat_id, round)` esattamente
come oggi. L'unica modifica in `jobs.py` è la scelta della `reply_markup`.

Scartata l'aggiunta di `user_id` a `lineup_confirmations`: il suo
`UNIQUE (chat_id, round)` non è allargabile con `ALTER TABLE ADD COLUMN` e servirebbe una
migrazione table-rebuild, per giunta cambiando la semantica della tabella che il percorso
privato usa già correttamente.

Tre tabelle nuove, tutte via `CREATE TABLE IF NOT EXISTS` (nessuna migrazione
`PRAGMA table_info`, che serve solo per colonne aggiunte a tabelle preesistenti):

```sql
group_participants (chat_id, user_id, joined_at, UNIQUE (chat_id, user_id))
group_rosters (chat_id PRIMARY KEY, closed_at TEXT)          -- NULL = iscrizioni aperte
group_lineup_confirmations (chat_id, round, user_id, UNIQUE (chat_id, round, user_id))
```

Tutte "disposable" come `sent_reminders`: nel peggior caso di perdita, una giornata di
promemoria torna a suonare e il roster va ricostruito.

`reminders/planner.py` **resta puro e invariato**, come in ADR 0021: il filtro è
bookkeeping DB applicato in `jobs.py`, non una nozione che la matematica dello scheduling
debba conoscere.

### 6. Canale

Il canale resta **senza bottone**, come da ADR 0021: è la superficie di produzione con
molti iscritti e nessun roster sensato da costruire.

## Limite intrinseco accettato

Chi non si registra mai e non conferma mai **non entra nel roster**, quindi "tutti hanno
confermato" resta un'approssimazione anche a implementazione completa. Non è un bug ed è
irrisolvibile con l'API Telegram attuale. Corollario del percorso zero-setup: in un gruppo
che non ha mai aperto le iscrizioni, il primo tap crea un roster di un solo elemento e
silenzia subito la giornata. Mitigazione scelta: finché le iscrizioni non sono chiuse, il
messaggio di conferma in gruppo invita ad aprirle con `/iscrizioni`.

## Consequences

- Tre tabelle nuove e i relativi metodi in `storage/repository.py` (tutto il SQL resta lì,
  ADR 0004).
- Nuovo comando `/iscrizioni`; `/ho_schierato` non risponde più `lineup_private_only` nei
  gruppi (quella stringa sparisce da `telegram/messages.py`).
- Cinque nuovi pattern di callback: `glineup:confirm:`, `glineup:undo:`, `roster:join`,
  `roster:close`, `roster:reopen`.
- `reminders/jobs.py`: cambia solo la scelta di `reply_markup` per gruppi e supergruppi.
- Follow-up operativo (BotFather, entrambi i bot): `ho_schierato` passa da scope
  *Direct Messages* a *Direct Messages + Group Chats*; va aggiunto `iscrizioni` con scope
  *Group Administrators*. Tracciato in `docs/HANDOFF.md`.
- Perimetro dei test invariato (deciso in sessione): logica pura + repository. Il flusso
  completo si verifica a mano sul bot dev — un `callback_query` nasce da un account utente
  e non è generabile con un bot token, quindi i tap sui bottoni non sono automatizzabili.
