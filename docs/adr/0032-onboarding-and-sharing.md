# ADR 0032: Onboarding e condivisione — deep link, benvenuto in gruppo, `/start`

- Status: accepted
- Date: 2026-09-10

## Contesto

Secondo punto della v1.4 (ADR 0030 §1): l'obiettivo del minor è **adozione**,
cioè rendere il bot più facile da diffondere fuori dal canale ufficiale. Oggi
mancano tutti e tre i pezzi:

- **`/start` butta il payload dei deep link.** `start_command`
  (`telegram/commands.py`) non legge `context.args`. I link
  `t.me/<bot>?start=<payload>` funzionano già lato Telegram — il payload arriva
  come primo argomento — ma il bot lo scarta in silenzio, quindi non c'è modo di
  sapere da dove arriva chi apre il bot.
- **Il bot non sa di essere stato aggiunto a un gruppo.** In `app.py` non è
  registrato nessun `ChatMemberHandler`: chi aggiunge il bot a un gruppo non
  riceve niente, e il gruppo resta senza promemoria finché qualcuno non scopre
  `/promemoria` da solo.
- **`/start` non ha una superficie di condivisione.** Il testo cita il canale
  (`CHANNEL_USERNAME`) ma la sua unica tastiera è il toggle
  attiva/disattiva; non c'è nessun percorso per portare il bot in un gruppo.

Vincoli ereditati: ADR 0030 §3 (le metriche restano fuori dal bot, con
l'eccezione esplicita di righe `bot_events` per azioni di dominio nuove, «es.
uno start da deep link»), ADR 0028 §1 (nessuna riga per le letture) e §2 (i
valori dei campi devono essere token senza spazi e **mai testo scritto
dall'utente**), ADR 0012 (le azioni chat-wide nei gruppi sono degli admin),
ADR 0018 Amendment (meno comandi, più bottoni).

## Decisione

### 1. Il payload del deep link è solo attribuzione, non un'azione

`/start` continua a fare esattamente quello che fa oggi. Se arriva un payload,
l'unico effetto in più è **una riga `bot_events`** che dice da dove viene quel
contatto.

Un payload che *attiva* i promemoria è stato scartato: il link è pubblico e
inoltrabile, quindi un click per curiosità creerebbe un'iscrizione che nessuno
ha chiesto, e in chat privata non c'è nessun gate admin a fermarlo. La
tastiera con "Attiva promemoria" è già a un tocco di distanza. Scartato anche
un payload che porti configurazione (offset preimpostati): moltiplicherebbe la
superficie da validare per un beneficio che nessuno ha chiesto.

### 2. Il payload è dato ostile: si valida prima di loggarlo

Chiunque può costruire `t.me/<bot>?start=<qualunque cosa>`. Quel valore
finirebbe in `source=` dentro una riga il cui formato è un **contratto** verso
la dashboard (ADR 0028 §2/§5): uno spazio o un `=` nel payload romperebbe il
parsing per chiave della dashboard, e il payload arbitrario finirebbe in chiaro
nei log.

Quindi: `parse_start_payload()` accetta solo `^[A-Za-z0-9_-]{1,32}$` — un
sottoinsieme di ciò che Telegram stesso permette nei deep link — e mappa
qualunque altra cosa su un token fisso. L'evento diventa:

- `action=start outcome=deeplink source=<slug>` per un payload valido;
- `action=start outcome=deeplink source=invalid` per uno malformato (il valore
  originale **non** viene loggato: è testo di ignoto);
- **nessuna riga** per uno `/start` senza payload, che resta una lettura come
  vuole ADR 0028 §1.

`parse_start_payload` è **pura**, quindi la validazione si testa senza Telegram.

### 3. Benvenuto quando il bot entra in un gruppo, senza iscrivere nulla

Nuovo `ChatMemberHandler(..., ChatMemberHandler.MY_CHAT_MEMBER)`: quando il bot
passa da fuori a dentro un gruppo o supergruppo, manda **un** messaggio di
presentazione con la stessa tastiera di `/promemoria`.

**Non crea nessuna subscription.** Attivare i promemoria resta un gesto
esplicito di un admin (ADR 0012), e iscrivere in automatico inquinerebbe il
conteggio di `outcome=created`, che ADR 0028 §4 tiene apposta come conteggio
delle iscrizioni vere.

Dettagli che il codice deve rispettare:

- **Solo transizioni reali di ingresso.** Si confrontano vecchio e nuovo stato:
  si parla solo se prima il bot era `left`/`kicked` e ora è
  `member`/`administrator`. Una promozione ad admin di un bot già nel gruppo,
  o una modifica di permessi, non è un ingresso e non deve rigenerare il
  benvenuto.
- **Solo gruppi e supergruppi.** Nei canali il benvenuto non ha senso (il
  canale ufficiale è seminato da `_post_init` con `origin='env'`) e in privato
  l'ingresso *è* `/start`.
- **Il gate `ALLOWED_CHAT_IDS` va ricontrollato a mano.** `ChatMemberHandler`
  non accetta il `filters=gate` che `app.py` passa ai `CommandHandler`, quindi
  l'handler ripete il controllo internamente, esattamente come fa `_gate` per i
  callback (ADR 0015).
- **La tastiera riflette lo stato reale.** Un bot rimosso e riaggiunto a una
  chat che ha ancora la sua subscription deve vedere "Disattiva promemoria":
  lo stato si rilegge dal repository, non si assume.
- Nei forum il benvenuto atterra dove lo mette Telegram; premere "Attiva
  promemoria" lega il topic in cui il bottone viene premuto, come da ADR 0025 e
  0031. Nessun trattamento speciale.

L'evento è `action=bot_added outcome=welcomed` (o `skipped` col gate attivo).

### 4. `/start`: due righe di tastiera, testo quasi invariato

La tastiera di `/start` in chat privata diventa:

1. il toggle attiva/disattiva che c'è già — **resta**: ADR 0018 Amendment §1 ha
   tolto dal testo la frase «oppure usa /promemoria_on» proprio perché quel
   bottone sta lì sotto, quindi rimuoverlo lascerebbe la prosa senza azione;
2. **"➕ Aggiungimi a un gruppo"**, bottone `url` verso
   `t.me/<username>?startgroup=true`, che apre il selettore di gruppi di
   Telegram.

Il bottone URL non ha `callback_data` e non genera nessun callback: zero
handler nuovi. Lo username arriva da `context.bot.username` al momento della
risposta, non da configurazione: è già così che `is_addressed_to_other_bot` lo
legge, e resta corretto su dev e prod senza una env var in più.

Scartati in questo giro il bottone verso il canale (il testo lo nomina già) e
un bottone "Cosa posso fare" verso `/help` (aggiungerebbe una superficie
callback per qualcosa che il testo già dice).

**Nessun comando `/invita`.** ADR 0018 Amendment spinge verso meno comandi e
più bottoni, e ADR 0025 aveva già rifiutato un comando dedicato per un motivo
analogo; sarebbe anche una voce di menù in più da incollare a mano su due bot
(ADR 0018 §Conseguenze).

Il bottone "Aggiungimi a un gruppo" ha senso solo in chat privata: in un gruppo
il bot **è** già dentro. `/start` in gruppo tiene quindi la tastiera di oggi.

## Alternative considerate

- **Deep link che attiva i promemoria** (`?start=on`) — §1: iscrizione senza
  consenso esplicito su un link inoltrabile.
- **Deep link che preimposta gli orari** — §1: superficie di validazione
  sproporzionata, e interazione poco chiara con ADR 0019/0020.
- **Loggare il payload grezzo** — §2: rompe il contratto di formato verso la
  dashboard e mette testo arbitrario nei log.
- **Iscrivere il gruppo all'ingresso del bot** — §3: chi aggiunge un bot è
  quasi sempre un admin, ma resta una subscription creata da un evento che
  nessuno ha confermato, e falsa `outcome=created`.
- **Nessun messaggio all'ingresso, solo un evento** — §3: silenzioso, ma butta
  via tutta la leva di onboarding.
- **Un comando `/invita`** — §4.
- **`origin` come colonna di attribuzione** in `subscriptions` — scartata:
  `origin` distingue `user` da `env` ed è ciò che protegge la riga del canale
  in `delete_user_subscription`/`prune_channel_subscriptions`; caricarla anche
  della provenienza la renderebbe ambigua. L'attribuzione è storia, e la storia
  sta in `bot_events` (ADR 0029).

## Conseguenze

- `telegram/commands.py`: `parse_start_payload()` pura; `start_command` legge
  `context.args`, emette l'evento e passa username e tipo di chat al builder.
- `telegram/keyboards.py`: `ACTION_ADD_TO_GROUP`, `build_start_keyboard()`
  (toggle + eventuale bottone url). `build_subscription_keyboard` resta com'è:
  è ancora la tastiera di `/promemoria` e del benvenuto.
- `telegram/chatmember.py` (nuovo modulo): l'handler `MY_CHAT_MEMBER` e la
  funzione pura che decide se una transizione è un ingresso. Sta fuori da
  `commands.py`/`callbacks.py` perché non è né un comando né un callback.
- `telegram/messages.py`: `group_welcome()`. `start()` invariato.
- `app.py`: registra il nuovo handler.
- `bot_events` guadagna due `action`: `start` (solo con payload) e `bot_added`.
  Aggiungere un'azione è sicuro per la dashboard; rinominarla no (ADR 0028).
- Nessuna migrazione, nessuna tabella nuova, nessun campo nuovo. Il motore dei
  promemoria non viene toccato (vincolo in-season di ADR 0030).
- `/help` non cambia: non ci sono comandi nuovi da elencare.
- Manuale, fuori dal codice: nessun setting BotFather nuovo. I link
  `t.me/<bot>?start=<slug>` si coniano a mano quando servono (uno per canale,
  post o gruppo da cui si vuole misurare la provenienza).
