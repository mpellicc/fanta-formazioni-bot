# ADR 0031: Bottoni di `/promemoria` consapevoli del topic

- Status: accepted
- Date: 2026-09-10

## Contesto

ADR 0025 ha reso le iscrizioni consapevoli dei topic: `subscriptions` ha un
`message_thread_id` nullable e la destinazione si (ri)lega **implicitamente**,
eseguendo `/promemoria_on` o `/personalizza_orari` dal topic desiderato. Il
binding è bidirezionale: rieseguire il comando da "General" (dove
`topic_thread_id()` ritorna `None`) sgancia il topic e riporta la consegna nella
chat principale.

Il buco, già registrato in `docs/HANDOFF.md` e messo in cima allo scope della
v1.4 da ADR 0030 §1, è che quel percorso esiste **solo da riga di comando**:

- `app.py:83` registra `/promemoria` → `subscription_status_command`, che
  risponde con `keyboards.build_subscription_keyboard(subscribed=…)`.
- Quel builder rende **un solo bottone**, `sub:on` *oppure* `sub:off`. In un
  forum con i promemoria già attivi l'utente vede solo "Disattiva promemoria":
  non c'è nessuna azione a tastiera per spostare la consegna in un topic.
- L'unica via resta `/promemoria_on` eseguito dal topic giusto, cioè un comando
  **legacy non promosso** — esattamente ciò che l'Amendment 2026-07-10 di
  ADR 0018 dice di non suggerire più fuori da `/help`.
- Il testo di `subscription_status()` non dice nemmeno **dove** atterrano i
  promemoria, quindi l'utente di un forum non ha modo di sapere se sono legati a
  un topic né a quale.

Il materiale per chiudere il buco c'è già tutto: `Chat.is_forum` sul messaggio
premuto, `topic_thread_id()` / `_query_thread_id()` per il topic corrente, e
`subscriptions.message_thread_id` per quello salvato.

Vincolo di stagione (ADR 0030): il motore dei promemoria
(`reminders/planner.py`, `reminders/jobs.py`) non si tocca.

## Decisione

### 1. Un terzo bottone opzionale, deciso da una funzione pura

`build_subscription_keyboard` guadagna un secondo bottone facoltativo, su una
riga propria sotto il toggle. Quale (o nessuno) lo decide
`keyboards.topic_action(...)`, funzione **pura** — nessun I/O, testabile come
`planner.py`:

```
topic_action(is_forum, subscribed, current_thread_id, bound_thread_id)
  -> "bind" | "unbind" | None
```

con queste regole, nell'ordine:

| condizione | esito |
|---|---|
| non è un forum, oppure non iscritti | `None` |
| `current` non è `None` e `current != bound` | `"bind"` |
| `bound` non è `None` (quindi `current == bound`, o `current` è General) | `"unbind"` |
| altrimenti (General, nessun topic legato) | `None` |

Le due righe centrali coprono i quattro casi reali: topic diverso da quello
legato → si offre lo spostamento; già nel topic legato → si offre lo sgancio;
in "General" con un topic legato → si offre lo sgancio (è la stessa azione che
oggi si ottiene rieseguendo `/promemoria_on` da lì); in "General" senza topic
legato → non c'è niente da fare.

**Perché non mostrarlo quando non si è iscritti**: lì il bottone visibile è
"Attiva promemoria", e `subscribe()` lega già il topic da cui viene premuto
(ADR 0025). Un secondo bottone direbbe la stessa cosa due volte.

Etichette (`ACTION_*` in `keyboards.py`, ADR 0018 §10):

- `ACTION_TOPIC_BIND = "Manda in questo topic"` (📌) — verbo + oggetto, stesso
  schema di `ACTION_SUBSCRIBE`/`ACTION_UNSUBSCRIBE`, e stesso lessico di
  `subscription_topic_bound()` ("Li manderò solo in questo topic").
- `ACTION_TOPIC_UNBIND = "Riporta in chat principale"` (📌), specchio di
  `subscription_topic_unbound()`.

### 2. Due callback_data costanti, nessuno stato nel payload

`CB_TOPIC_BIND = "sub:topic:on"` e `CB_TOPIC_UNBIND = "sub:topic:off"`, senza
payload — coerenti con ADR 0015 (le tastiere restano stateless attraverso i
riavvii) e più forti del bitmask degli offset: **il topic di destinazione non
viaggia affatto nel callback_data**, si rilegge dal messaggio premuto via
`_query_thread_id(query)`, che è per costruzione il topic in cui il bottone
vive. Una tastiera vecchia non può quindi consegnare a un topic sbagliato: al
massimo agisce sul topic in cui è effettivamente visibile.

`CB_TOPIC_UNBIND` forza `None` ignorando il topic premuto: è l'unico modo di
sganciare da dentro il topic legato senza costringere l'utente a salire in
"General".

### 3. Handler dedicati, non un riuso di `sub:on`

Si potrebbe far puntare "Manda in questo topic" a `sub:on`, che già rilega il
topic. Rifiutato: `subscribe()` **crea** l'iscrizione se manca, quindi una
tastiera premuta dopo una disattivazione la resusciterebbe silenziosamente, e
il testo di conferma parlerebbe di attivazione anziché di spostamento.

Nasce quindi in `commands.py` una funzione core condivisa:

```
rebind_topic(chat, message_thread_id, repository) -> RebindResult
```

che **non crea nulla**: legge la subscription, e se non esiste torna
`subscribed=False`; se esiste e la destinazione cambia chiama
`repository.update_subscription_thread` (già presente, ADR 0025). Come in
ADR 0025 **non ripianifica**: `PlannedReminder` non porta thread id e
`send_reminder_job` rilegge la subscription al momento dell'invio, quindi il
motore resta intatto — vincolo ADR 0030 rispettato.

Gli offset non vengono mai toccati da questo percorso (invariante ADR 0019/0020).

### 4. Permessi: come `sub:on`/`sub:off`

Spostare la destinazione cambia dove atterrano i promemoria **di tutto il
gruppo**, quindi è un'azione chat-wide e passa dallo stesso gate admin degli
altri due callback: `_may_manage` (ADR 0012), con il toast `admin_only()` per
chi non lo è.

Il bottone resta **visibile a tutti**. Nasconderlo ai non-admin richiederebbe
una `get_chat_member` dentro `subscription_status_command`, che oggi è
read-only e non fa nessuna chiamata API: un round-trip in più su ogni
`/promemoria` per un bottone che il gate respinge comunque. Stessa scelta,
implicita, già in vigore per il toggle.

### 5. Il testo dello stato dice la destinazione, ma solo nei forum

`messages.subscription_status()` guadagna un frammento finale opzionale:

- "📌 Li mando in questo topic." quando il topic legato è quello corrente;
- "📌 Li mando in un altro topic di questo gruppo." quando è legato altrove
  (il nome del topic non è recuperabile: ADR 0025 §"No topic name stored");
- "📌 Li mando nella chat principale." quando non c'è binding.

**Solo se `chat.is_forum`.** Nei gruppi normali, nei canali e in privato il
`message_thread_id` è strutturalmente `NULL` e il concetto non esiste: dirlo
sarebbe rumore su superfici che oggi rendono un testo perfetto. Il testo
esistente resta byte-identico lì.

### 6. Evento `topic_rebind`

`rebind_topic` emette `log_event("topic_rebind", …)` con outcome
`bound` / `unbound` / `noop` / `not_subscribed`, riusando le chiavi già in
vocabolario (`chat_type`, `thread_id`) come impone ADR 0028 §Conseguenze. È un
`action` nuovo perché è un cambio di destinazione, non un'iscrizione: contarlo
dentro `subscribe`/`outcome=noop` sporcherebbe le metriche di adozione.

Nessuna riga in `subscription_events`: ADR 0025 ha già stabilito che lo
spostamento di topic non è un evento di ciclo di vita.

## Alternative considerate

- **Un bottone che elenca i topic del gruppo.** Impossibile: la Bot API non
  espone la lista dei topic di un forum (stesso limite che in ADR 0025 ha
  impedito di mostrare il *nome* del topic). L'unico topic conoscibile è quello
  in cui si trova il messaggio.
- **Riusare `sub:on`** per il bind — rifiutato in §3 (resurrezione silenziosa
  dell'iscrizione, testo di conferma sbagliato).
- **Codificare il thread id nel callback_data** (`sub:topic:on:<id>`) —
  rifiutato: rileggerlo dal messaggio premuto è sia più corto sia più sicuro
  (§2), e il thread id del messaggio è sempre disponibile quando il messaggio è
  ancora accessibile.
- **Mostrare il bottone anche ai non iscritti** — rifiutato in §1: duplica
  "Attiva promemoria", che lega già il topic.
- **Aggiungere un comando `/promemoria_qui`** — già rifiutato da ADR 0025, e
  ADR 0018 (Amendment) spinge nella direzione opposta: meno comandi, più
  bottoni.
- **Riga di destinazione sempre presente nei gruppi** — rifiutata in §5.

## Conseguenze

- `keyboards.py`: due `ACTION_*`, due `CB_*`, la funzione pura `topic_action` e
  un parametro keyword-only in più su `build_subscription_keyboard`
  (default `None` = tastiera identica a oggi). Le quattro call site esistenti
  che non hanno contesto forum non cambiano comportamento.
- `commands.py`: `rebind_topic` + `RebindResult`; `subscription_status_command`
  passa `is_forum` e i due thread id al builder e al testo.
- `callbacks.py`: `topic_bind_callback` / `topic_unbind_callback`, registrati
  con pattern ancorati come gli altri, entrambi dietro `_gate` + `_may_manage`.
  Entrambi riscrivono il messaggio premuto in place (`_edit_text`) con lo stato
  aggiornato — quindi dopo un bind il bottone diventa "Riporta in chat
  principale" senza un nuovo messaggio.
- `messages.py`: tre frammenti nuovi per la destinazione (§5).
- Il motore dei promemoria non cambia di una riga: nessuna ripianificazione,
  nessun campo nuovo, nessuna migrazione (`message_thread_id` esiste da
  ADR 0025).
- `docs/ARCHITECTURE.md` e `docs/HANDOFF.md`: il buco "bottoni non
  topic-aware" si chiude e va tolto dai gap noti.
