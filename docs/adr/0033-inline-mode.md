# ADR 0033: Inline mode — condividere la prossima scadenza da qualsiasi chat

- Status: accepted
- Date: 2026-09-10

## Contesto

La v1.5 (ADR 0030 §2) esiste per una cosa sola: `@bot` digitato in una chat
qualunque condivide la card della prossima scadenza **senza che nessuno debba
aggiungere il bot da nessuna parte**. È la leva di diffusione più forte del
piano, ed è tenuta fuori dalla v1.4 perché è una superficie Telegram nuova, con
un setting BotFather e un giro di test manuali propri.

Stato del codice oggi:

- **Non esiste niente**: nessuna occorrenza di `InlineQuery`/`inline_query` in
  `src/` o `tests/`.
- **Il dato è già pronto**: `planner.next_deadline(matchdays, margin, now)` è
  puro e `messages.next_deadline()` esiste; `next_deadline_command` fa già
  esattamente questa lettura. L'inline mode non ha bisogno di logica nuova di
  dominio, solo di una superficie nuova.
- **`ALLOWED_CHAT_IDS` non può gatarla.** In `app.py` la whitelist è un
  `filters.Chat(...)` sui `CommandHandler`, e `_gate` (`telegram/callbacks.py`)
  la ripete per i callback leggendo `query.message.chat.id`. Una `InlineQuery`
  **non ha una chat**: porta solo `from_user`. Senza un gate proprio, il bot
  dev — oggi muto fuori dalle chat whitelistate — risponderebbe a chiunque ne
  conosca lo username. È la stessa classe di buco trovata in ADR 0032 per
  `ChatMemberHandler`, ma qui non c'è nemmeno un `chat_id` su cui ripiegare.
- **La card invecchia**: `messages.next_deadline()` contiene il tempo rimanente
  e `answer_inline_query` ha `cache_time` con default **300 s**, quindi
  Telegram potrebbe servire un countdown vecchio di cinque minuti.

## Decisione

### 1. Due risultati: la scadenza e l'invito

Una query inline (qualunque testo, anche vuoto) restituisce sempre **due**
`InlineQueryResultArticle`:

1. **La prossima scadenza** — giornata, data/ora, tempo rimanente: esattamente
   `messages.next_deadline()`, la stessa voce di `/prossima_scadenza`. A
   stagione finita la card diventa `messages.no_upcoming_deadline()`: la
   posizione resta occupata, così non esiste un caso in cui l'inline non
   risponde e l'utente resta a fissare una lista vuota.
2. **L'invito** — una riga di presentazione più il link al bot, sulla scia del
   bottone "Aggiungimi a un gruppo" di ADR 0032. È il risultato che trasforma
   una condivisione in adozione.

L'ordine non è negoziabile: il primo risultato è quello che si ottiene
premendo invio senza scegliere, e deve essere l'informazione, non la pubblicità.

### 2. `ALLOWED_USER_IDS`, gate proprio dell'inline

Nuova env var, letta come `allowed_chat_ids` (stessa `NoDecode` +
`field_validator`, stessa semantica: **vuota = aperta**). Se valorizzata,
l'handler risponde solo a quegli `from_user.id`; a tutti gli altri risponde con
una lista **vuota**, che è il modo di Telegram di dire "nessun risultato" senza
rivelare che il bot esiste.

Perché una var nuova e non "inline spento quando `ALLOWED_CHAT_IDS` è
valorizzata": spegnendola non si potrebbe **provare l'inline sul bot dev**, che
è esattamente dove va provata prima di arrivare in produzione. Il costo è un
valore in più negli environment GitHub (ADR 0010), da valorizzare **solo in
dev**; in produzione resta vuota e l'inline è aperto a tutti, che è il punto
della feature.

Il gate è una funzione pura, `inline_allowed(user_id, allowed_user_ids)`, così
la tabella dei casi si testa senza Telegram.

### 3. `cache_time` basso, testo unico

`answer_inline_query(..., cache_time=30)`. Si tiene **una sola** voce per la
prossima scadenza (`messages.next_deadline()`, condivisa con
`/prossima_scadenza`) e si accetta al massimo mezzo minuto di scarto sul
countdown.

L'alternativa — una card senza countdown, cacheabile a lungo — avrebbe
richiesto un secondo testo quasi identico al primo in `messages.py`, cioè due
voci da tenere allineate a mano per risparmiare traffico che a questi volumi
non è un problema. `cache_time=0` è scartato: Telegram lo sconsiglia e ogni
battitura nella barra genererebbe una richiesta.

`is_personal` resta **falso**: la card non dipende da chi la chiede, quindi la
cache può essere condivisa fra utenti.

### 4. Si logga la condivisione, non la digitazione

Telegram distingue la query digitata (`inline_query`) dal risultato
effettivamente scelto e inviato (`chosen_inline_result`). Si registra **solo il
secondo**: è la condivisione vera, mentre loggare le query conterebbe le
battiture nella barra di ricerca — cioè traffico, che ADR 0028 §1 vieta
esplicitamente.

L'evento non appartiene a nessuna chat: `ChosenInlineResult` non porta un
`chat_id`. Si usa quindi `record_process_event` (`telegram/events.py`), che
esiste esattamente per questo ed è **DB-only**, perché il prefisso `chat_id=`
della riga di log è un contratto verso la dashboard (ADR 0028 §5). Azione
`inline_share`, outcome `deadline` o `invite` secondo quale delle due card è
stata scelta; `user_id` viaggia nei campi e finisce nella colonna promossa
(`record_event` promuove `chat_type`, `user_id`, `round`).

**Serve il setting BotFather `/setinlinefeedback`** perché quell'update venga
recapitato: senza, l'inline funziona lo stesso ma non si misura niente. Va
messo **al 100%** sui due bot; è un setting manuale come tutti gli altri di
ADR 0018.

## Alternative considerate

- **Un solo risultato (la scadenza)** — più immediato, ma butta via la metà
  della feature che serve all'adozione: chi vede la card in una chat altrui non
  ha nessun percorso verso il bot.
- **Inline spento quando `ALLOWED_CHAT_IDS` è valorizzata** — §2: renderebbe
  impossibile il giro di test in dev, che è la ragione per cui il bot dev
  esiste.
- **Nessun gate** — §2: romperebbe l'invariante "il bot dev non risponde a
  estranei" (ADR 0010).
- **Card senza countdown con cache lunga** — §3: due testi quasi uguali da
  tenere allineati.
- **Loggare `inline_query`** — §4: conta le battiture, non le condivisioni.
- **Cercare dentro la query** (es. `@bot 12` per la giornata 12) — scartata:
  nessuno l'ha chiesta, e trasformerebbe una card da condividere in una
  superficie di ricerca con i suoi errori da gestire. Il testo della query
  viene deliberatamente **ignorato**.

## Conseguenze

- `config.py`: `allowed_user_ids` con il suo validator, gemello di
  `allowed_chat_ids`. Nuova riga nella tabella env di `docs/ARCHITECTURE.md`.
- `telegram/inline.py` (nuovo modulo): `inline_allowed()` pura, il builder dei
  due risultati, i due handler (`InlineQueryHandler`,
  `ChosenInlineResultHandler`) e la loro `register(application)`, sul modello di
  `telegram/chatmember.py` (ADR 0032).
- `telegram/messages.py`: i testi dei titoli/descrizioni delle due card e il
  corpo dell'invito. `next_deadline()` e `no_upcoming_deadline()` sono riusati
  invariati.
- `app.py`: registra il modulo.
- `bot_events` guadagna l'azione `inline_share`. Aggiungere un'azione è sicuro
  per la dashboard, rinominarla no (ADR 0028).
- Nessuna migrazione, nessuna tabella nuova, nessun campo nuovo. Il motore dei
  promemoria non viene toccato: l'inline è una lettura pura, non tocca
  `subscriptions` né la pianificazione.
- **Manuale, su entrambi i bot**: attivare *Inline Mode* su BotFather (con un
  placeholder, es. "Cerca la prossima scadenza") e `/setinlinefeedback` al
  100%. Su dev, valorizzare `ALLOWED_USER_IDS` nell'environment GitHub.
  Finché Inline Mode non è attivo su BotFather, il codice è inerte: nessun
  update arriva.
