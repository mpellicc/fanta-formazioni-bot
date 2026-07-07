# Session handoff — FantaFormazioni Bot

> Scritto il 2026-07-07 al termine della sessione di riscrittura v2. Destinatario: la prossima sessione di Claude Code (e Matteo). Aggiornarlo (o snellirlo) alla fine delle sessioni significative; per i fatti volatili (PR aperte, versione in prod) verificare sempre lo stato reale con `gh`.

## 1. Documenti essenziali da leggere (in quest'ordine)

1. **`CLAUDE.md`** (root) — comandi, struttura, invarianti, git workflow. Sempre per primo.
2. **`docs/ARCHITECTURE.md`** — componenti, flussi (startup / refresh / reminder), schema DB, tabella env vars.
3. **`docs/adr/0001–0015`** — una ADR per decisione architetturale. **Leggere la ADR pertinente prima di toccare una scelta architetturale; scrivere una nuova ADR quando se ne prende una.** Le più consultate: 0005 (scheduling esatto), 0008 (+ amendment: subscription `origin`, già pensata per i canali user-owned), 0010 (dev/prod environments), 0011 (release flow), 0012 (comandi subscription, pattern admin-only da riusare), 0015 (tastiere inline: bitmask stateless in callback_data, ConversationHandler per input libero).
4. **`docs/DEPLOY.md`** — VM Oracle, environments GitHub, workflow CI/CD, convenzioni di merge, operations.

## 2. Cosa è stato fatto e perché

**Riscrittura completa (v1 → v2, rilasciata come 0.9.0, oggi in prod v0.11.0).** La v1 (Poetry, PTB 21, polling ogni 5s, datetime naive, locale di sistema, zero test/CI) è stata sostituita da zero: uv+ruff+mypy strict+pytest, PTB ~22.8, job `run_once` a orari esatti con dedupe su SQLite, kickoff "pulito" + `DEADLINE_MARGIN` configurabile, provider calendario pluggabile (fixturedownload CSV UTC), testi italiani in HTML parse mode. Motivazioni dettagliate nelle ADR 0001–0009.

**Infrastruttura (tutta funzionante e verificata):**
- VM **Oracle Cloud Always Free** `VM.Standard.E2.1.Micro` (x86, 1GB RAM + 2GB swap), IP `130.110.70.70`, utente `ubuntu`. SSH: alias `fantabot` in `~/.ssh/config` (chiave `~/.ssh/oracle_fantabot`); chiave di deploy per Actions: `~/.ssh/fantabot_deploy` (privata nel secret `SSH_KEY`).
- Era prevista la A1.Flex (ARM) ma è sempre out-of-capacity: per questo l'immagine è **multi-arch** (amd64+arm64). Migrare ad A1 quando c'è capacità è banale (stessa procedura DEPLOY.md).
- **Due istanze sulla stessa VM**: prod (`~/fantaformazionibot`, immagine `:latest`, canale @fantaformazionireminders id `-1002189068048`) e dev (`~/fantaformazionibot-dev`, immagine `:dev`, debug chat `-1002171697436`). Due bot Telegram distinti (il polling vieta token condivisi).
- **Config gestita dalla pipeline** (ADR 0010): il deploy riscrive `.env` e `compose.yaml` sulla VM dai secrets/vars degli environments GitHub `production`/`development`. MAI modificarli a mano sulla VM. Cambio config = aggiornare il valore su GitHub → rilanciare Deploy.
- Il bot **dev risponde solo a Matteo** (user id `41755391`) e alla debug chat, via `ALLOWED_CHAT_IDS` (vuota in prod = aperto).

**Flusso di lavoro (ADR 0011):**
- `dev` = default branch; feature → PR su `dev` → **squash merge** → deploy automatico del bot dev.
- Release: workflow **Prepare release** su `dev` (scelta patch/minor/major) → bumpa `pyproject.toml`, apre release PR verso `main` → Matteo la approva (l'autore è github-actions[bot], quindi può) e mergia con **merge commit** (MAI squash verso main) → deploy prod → tag `vX.Y.Z` + GitHub Release automatici.
- `main` ha branch protection (1 review); "Automatically delete head branches" attivo.
- Fix di sicurezza: token dei workflow a minimo privilegio (alert CodeQL risolti).

**Bug notevoli risolti (da conoscere):**
- Cambiare `CHANNEL_CHAT_ID` lasciava la vecchia subscription nel DB (reminder duplicati a entrambe le chat). Fix: colonna `origin` (`env`/`user`) + pruning all'avvio delle sole righe channel `origin='env'` stale. Le future subscription utente (`origin='user'`) non vengono mai toccate.
- Docker: `uv sync` senza `--no-editable` produce un venv che punta a `/app/src` inesistente nello stage finale.

## 3. Cosa c'è da fare e come

**Roadmap funzionale (in ordine di priorità espressa da Matteo) — tutta rilasciata in prod con v0.11.0:**
1. ✅ **Promemoria privati per utente e per gruppo** (PR #15): `/promemoria_on`, `/promemoria_off`, `/promemoria`; nei gruppi on/off sono solo per admin. Decisioni in **ADR 0012**.
2. ✅ **Orari di notifica personalizzabili per subscription** (PR #16): `/personalizza_orari [offset...|default]` aggiorna `reminder_offsets` sulla riga della chat corrente (auto-iscrive se assente); senza argomenti mostra gli orari attuali. Validazione: unità s/m/h, 1 minuto–7 giorni, max 10 offset. Admin-only nei gruppi come `/promemoria_on`. Decisioni in **ADR 0013**.
3. ✅ **Provider football-data.org alternativo a fixturedownload + alert di staleness** (PR #17): `CALENDAR_PROVIDER` è ora un enum (`fixturedownload`/`football-data-org`, valori invariati per compatibilità); il secondo provider si attiva impostando `CALENDAR_PROVIDER=football-data-org` + `FOOTBALL_DATA_API_KEY` (switch manuale, non automatico). Il refresh giornaliero avvisa su `DEBUG_CHAT_ID` se la prossima giornata ha ancora un kickoff placeholder (`00:00` UTC) a meno di 3 giorni dalla scadenza. Decisioni in **ADR 0014**.

4. 🚧 **Inline keyboard (bottoni callback)** — in lavorazione (branch `feature/inline-keyboards`, non ancora mergiata): `/start`, `/promemoria` e `/personalizza_orari` (senza argomenti) hanno bottoni sopra la stessa logica di subscribe/unsubscribe/set-offsets; griglia di 8 preset (2g/24h/12h/3h/1h/30m/10m/5m) con stato codificato in `callback_data` (stateless), bottone "Personalizzati" che apre una `ConversationHandler` con `ForceReply` per un input libero tipo `2g,12h,10m`. Decisioni in **ADR 0015**. Restano da fare prima del merge: aggiornamento BotFather non necessario (nessun nuovo comando), ma verifica manuale end-to-end sul bot dev (vedi checklist ADR 0015/piano di sessione) e review di Matteo.

Dopo il merge dell'inline keyboard, la prossima feature è la prima idea v2.0 qui sotto (canali user-owned), da pianificare.

**Idee UX per una futura v2.0 (valutate 2026-07-07):**

- ⏭️ **Canali di lega user-owned — PROSSIMA FEATURE DA PIANIFICARE dopo l'inline keyboard**. Un utente aggiunge il bot come admin del proprio canale Telegram (fuori dal canale ufficiale @fantaformazionireminders) per ricevere lì i promemoria della propria lega. Contesto utile per la pianificazione:
  - **Perché serve un meccanismo diverso dai comandi**: i canali non possono inviare messaggi/comandi al bot (solo i post del canale stesso), quindi `/promemoria_on` è strutturalmente inutilizzabile lì. L'unico segnale disponibile è l'evento Telegram `my_chat_member` (il bot viene promosso/rimosso da admin del canale).
  - **Plumbing già pronto, niente schema da toccare**: `Subscription.chat_type` già accetta `"channel"` (è il tipo usato dalla subscription env-seeded, vedi `models.py` e i test in `test_repository.py` con `ENV_CHANNEL`); l'`origin='user'` già protegge dal pruning di `prune_channel_subscriptions` — l'amendment ADR 0008 lo dice esplicitamente: *"user rows — including channels users will add the bot to — are never touched by config changes"*. Quindi: creare la subscription è un `upsert_subscription(..., chat_type="channel", origin="user")` come già fa `subscribe_command` in `telegram/commands.py`, nessuna nuova colonna/tabella.
  - **Cosa manca**: nessun handler di questo tipo esiste oggi (`grep -r ChatMemberHandler src/` non trova nulla). Serve un `ChatMemberHandler(callback, ChatMemberHandler.MY_CHAT_MEMBER)` registrato in `app.py`, che legge `update.my_chat_member` (`ChatMemberUpdated`: `old_chat_member`/`new_chat_member`, con `.status`) per distinguere promozione ad admin (→ subscribe) da rimozione/demozione (→ unsubscribe, riusando `delete_user_subscription`).
  - **Setting BotFather da attivare**: "Channel Admin Rights", limitato a *Post Messages* (nessun altro permesso serve).
  - **Decisioni aperte da prendere in ADR** (non ancora scelte):
    1. Iscrizione automatica alla promozione ad admin, o richiedere una conferma esplicita del proprietario (e come, dato che il canale non può mandare comandi — forse un comando in privato tipo `/conferma_canale`)?
    2. Offset di default: riusare `settings.reminder_offsets` come per gruppi/privato, presumibilmente sì.
    3. Come comunicare all'owner che l'iscrizione è avvenuta/revocata, visto che il bot non può scrivere nel canale se non ha (o ha perso) i permessi di post — probabilmente un messaggio privato all'utente che ha effettuato il cambio membership (`update.my_chat_member.from_user`), sul modello di come `errors.py` scrive già su `DEBUG_CHAT_ID`.
    4. `/personalizza_orari` e `/promemoria` restano non invocabili nel canale per lo stesso motivo (niente comandi) — vanno quindi lasciati eseguibili solo in privato/gruppo, oppure serve un modo per l'owner di gestirli comunque (es. comandi in privato che operano sul canale specificando l'id)? Da decidere se è nello scope o rimandato.
- ✅ **Inline keyboard (bottoni callback)** — vedi punto 4 sopra, ADR 0015.
- **Inline Mode** (setting BotFather + `InlineQueryHandler`): `@bot` in una chat qualsiasi per condividere la card della prossima scadenza senza aggiungere il bot alla chat. Rimandata dopo i canali.
- Setting BotFather verificati e da lasciare così: **Allow Groups ON**, **Group Privacy ON** (il bot vede solo i /comandi nei gruppi — non disattivare); Admin Rights / Guard / Secretary / Guest / Bot-to-Bot / Threads non servono al caso d'uso attuale (Admin Rights per i canali va invece attivato per la feature sopra). "Restrict bot usage" solo sul bot dev (ridondante con `ALLOWED_CHAT_IDS`, ma difesa in più). Privacy Policy: oggi vale quella standard di Telegram; se il bot cresce, basterebbe una policy di tre righe (memorizziamo solo chat_id e orari).

**Operativo/monitoraggio:**
- **BotFather, su entrambi i bot (dev e prod)**: ✅ lista comandi aggiornata con `promemoria_on`/`promemoria_off`/`promemoria`/`personalizza_orari`. Scope: on/off e `personalizza_orari` visibili solo in *Direct Messages* + *Group Administrators* (Group Chats OFF: i non-admin riceverebbero solo il rifiuto); `/promemoria` visibile ovunque. Gli scope regolano solo la visibilità nel menu, l'enforcement admin è nel codice.
- La stagione 2026-27 inizia il **22 agosto 2026**: il primo reminder reale parte ~21 agosto. Verificare che arrivi sul canale (finora testati solo i comandi, non un reminder "live" in prod).
- Gli orari delle giornate lontane nel CSV sono placeholder (es. 00:00): si sistemano da soli col refresh giornaliero delle 02:00.
- **Da fare**: aggiungere il secret repo-level `FOOTBALL_DATA_API_KEY` su GitHub (Settings → Secrets and variables → Actions → Secrets) — senza, il provider football-data.org (ADR 0014) non è attivabile in caso di emergenza. Non fatto perché richiede una registrazione esterna, non automatizzabile da qui.
- Migrazione VM a A1.Flex: **ancora out-of-capacity** (ritentato il 2026-07-07, nessuna disponibilità). Procedura passo-passo in `docs/DEPLOY.md` § "Migrating to a new VM".

**Come lavorare con Matteo (vedi anche memoria persistente):**
- Stile consultivo: **proporre opzioni con trade-off** (AskUserQuestion) prima di decisioni di design/UX/infra; non applicare default in silenzio, anche su dettagli.
- **ADR prima del codice** per ogni decisione architetturale.
- I merge delle PR li fa **lui**; commit e push come comandi separati.
- **Niente `Co-Authored-By` nei commit né footer "Generated with" nelle PR.**
- Prima di dichiarare finito: `uv run ruff check && uv run ruff format --check && uv run mypy src && uv run pytest` tutti verdi.

**Stato al momento dell'handoff (agg. 2026-07-07, sessione inline keyboard):** **prod = v0.11.0** (invariata, non ancora rilasciata questa feature). `dev`/`main` allineati come da handoff precedente. Sessione corrente: branch **`feature/inline-keyboards`** (da `dev`, non ancora aperta PR) con ADR 0015 scritta e implementazione completa — `telegram/keyboards.py` (builder tastiere + codec `callback_data` stateless), `telegram/callbacks.py` (`CallbackQueryHandler` + `ConversationHandler` per l'input libero "Personalizzati"), logica subscribe/unsubscribe/set-offsets estratta in `commands.py` e riusata da entrambi. Unità `g` aggiunta a `parse_duration`; unità `s` non più mostrata nei testi ma ancora accettata dal parser. `ruff check`, `ruff format --check`, `mypy src`, `pytest` (65 test, inclusi i nuovi `test_keyboards.py`) tutti verdi. **Non ancora fatto**: verifica manuale end-to-end sul bot dev (toggle, griglia, Personalizzati, Indietro, /annulla, timeout, rifiuto non-admin in gruppo), apertura PR, aggiornamento di questo HANDOFF a merge avvenuto. Azioni pendenti non bloccanti ereditate: secret `FOOTBALL_DATA_API_KEY` da aggiungere; migrazione VM ad A1.Flex bloccata da mancanza di capacità Oracle.

**Prossimo lavoro pianificato**: 1) completare e mergiare `feature/inline-keyboards` (verifica manuale sul bot dev, poi PR su `dev`); 2) dopo il merge, design + implementazione dei **canali di lega user-owned**. Il contesto tecnico per i canali (perché serve `my_chat_member`, cosa nello schema è già pronto, cosa manca, le 4 decisioni aperte) è raccolto nella sezione "Idee UX per una futura v2.0" sopra — parti da lì. ADR 0008 (+ amendment) e ADR 0012 sono citate lì solo come riferimento implementativo (schema `origin`, pattern admin-only); leggerle non sostituisce la sezione, la completa. Segui lo stile ADR-first anche per i canali: AskUserQuestion sulle 4 decisioni aperte prima di finalizzare il design, nuova ADR (0016) prima di implementare.
