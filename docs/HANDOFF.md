# Session handoff — FantaFormazioni Bot

> Scritto il 2026-07-07 al termine della sessione di riscrittura v2. Destinatario: la prossima sessione di Claude Code (e Matteo). Aggiornarlo (o snellirlo) alla fine delle sessioni significative; per i fatti volatili (PR aperte, versione in prod) verificare sempre lo stato reale con `gh`.

## 1. Documenti essenziali da leggere (in quest'ordine)

1. **`CLAUDE.md`** (root) — comandi, struttura, invarianti, git workflow. Sempre per primo.
2. **`docs/ARCHITECTURE.md`** — componenti, flussi (startup / refresh / reminder), schema DB, tabella env vars.
3. **`docs/adr/0001–0011`** — una ADR per decisione architetturale. **Leggere la ADR pertinente prima di toccare una scelta architetturale; scrivere una nuova ADR quando se ne prende una.** Le più consultate: 0005 (scheduling esatto), 0008 (+ amendment: subscription `origin`), 0010 (dev/prod environments), 0011 (release flow).
4. **`docs/DEPLOY.md`** — VM Oracle, environments GitHub, workflow CI/CD, convenzioni di merge, operations.

## 2. Cosa è stato fatto e perché

**Riscrittura completa (v1 → v2, rilasciata come 0.9.0, oggi in prod v0.10.0).** La v1 (Poetry, PTB 21, polling ogni 5s, datetime naive, locale di sistema, zero test/CI) è stata sostituita da zero: uv+ruff+mypy strict+pytest, PTB ~22.8, job `run_once` a orari esatti con dedupe su SQLite, kickoff "pulito" + `DEADLINE_MARGIN` configurabile, provider calendario pluggabile (fixturedownload CSV UTC), testi italiani in HTML parse mode. Motivazioni dettagliate nelle ADR 0001–0009.

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

**Roadmap funzionale (in ordine di priorità espressa da Matteo):**
1. ✅ **Promemoria privati per utente e per gruppo** — fatto (PR #15, 2026-07-07, su dev; in prod alla prossima release): `/promemoria_on`, `/promemoria_off`, `/promemoria`; nei gruppi on/off sono solo per admin. Decisioni in **ADR 0012**.
2. ✅ **Orari di notifica personalizzabili per subscription** — fatto (2026-07-07, branch `feature/custom-reminder-offsets`, non ancora mergiata): `/personalizza_orari [offset...|default]` aggiorna `reminder_offsets` sulla riga della chat corrente (auto-iscrive se assente); senza argomenti mostra gli orari attuali. Validazione: unità s/m/h, 1 minuto–7 giorni, max 10 offset. Admin-only nei gruppi come `/promemoria_on`. Decisioni in **ADR 0013**.
3. Eventuale provider API strutturata in alternativa a fixturedownload (ADR 0007: nuova classe + entry nella factory + `CALENDAR_PROVIDER`).

**Idee UX per una futura v2.0 (valutate 2026-07-07, non pianificate):**
- **Inline keyboard (bottoni callback)** al posto dei soli comandi: `/start` in privato con bottone "Attiva promemoria", `/promemoria` con toggle on/off, scelta degli orari a bottoni (naturale insieme alla feature 2). È solo codice PTB (`InlineKeyboardMarkup` + `CallbackQueryHandler`), nessun setting BotFather.
- **Inline Mode** (setting BotFather + `InlineQueryHandler`): `@bot` in una chat qualsiasi per condividere la card della prossima scadenza senza aggiungere il bot alla chat.
- **Canali di lega user-owned**: un utente aggiunge il bot come admin del proprio canale (setting BotFather "Channel Admin Rights" con solo *Post messages*) → un `ChatMemberHandler` su `my_chat_member` crea/cancella la subscription `origin='user'`, `chat_type='channel'`. Caso già previsto dall'amendment ADR 0008; è l'unica via per i canali, che non possono inviare comandi. Da decidere: iscrizione automatica o conferma del proprietario.
- Setting BotFather verificati e da lasciare così: **Allow Groups ON**, **Group Privacy ON** (il bot vede solo i /comandi nei gruppi — non disattivare); Admin Rights / Guard / Secretary / Guest / Bot-to-Bot / Threads non servono al caso d'uso. "Restrict bot usage" solo sul bot dev (ridondante con `ALLOWED_CHAT_IDS`, ma difesa in più). Privacy Policy: oggi vale quella standard di Telegram; se il bot cresce, basterebbe una policy di tre righe (memorizziamo solo chat_id e orari).
- Priorità indicativa v2.0: inline keyboard → Inline Mode → canali user-owned.

**Operativo/monitoraggio:**
- **BotFather, su entrambi i bot (dev e prod)**: lista comandi aggiornata con `promemoria_on`/`promemoria_off`/`promemoria`. Scope: on/off visibili solo in *Direct Messages* + *Group Administrators* (Group Chats OFF: i non-admin riceverebbero solo il rifiuto); `/promemoria` visibile ovunque. Gli scope regolano solo la visibilità nel menu, l'enforcement admin è nel codice. Da fare: aggiungere `personalizza_orari` alla lista con lo stesso scope di on/off (ADR 0013).
- La stagione 2026-27 inizia il **22 agosto 2026**: il primo reminder reale parte ~21 agosto. Verificare che arrivi sul canale (finora testati solo i comandi, non un reminder "live" in prod).
- Gli orari delle giornate lontane nel CSV sono placeholder (es. 00:00): si sistemano da soli col refresh giornaliero delle 02:00.
- Tentare ogni tanto la migrazione a VM A1.Flex (gratis, 6+ GB). Procedura: nuova VM → step DEPLOY.md → aggiornare secret `SSH_HOST` → rilanciare i deploy.

**Come lavorare con Matteo (vedi anche memoria persistente):**
- Stile consultivo: **proporre opzioni con trade-off** (AskUserQuestion) prima di decisioni di design/UX/infra; non applicare default in silenzio, anche su dettagli.
- **ADR prima del codice** per ogni decisione architetturale.
- I merge delle PR li fa **lui**; commit e push come comandi separati.
- **Niente `Co-Authored-By` nei commit né footer "Generated with" nelle PR.**
- Prima di dichiarare finito: `uv run ruff check && uv run ruff format --check && uv run mypy src && uv run pytest` tutti verdi.

**Stato al momento dell'handoff (agg. 2026-07-07, sessione feature #2):** prod = v0.10.0; dev contiene in più la feature subscription utente/gruppo (PR #15 mergiata, bot dev deployato) non ancora rilasciata in prod. Il branch `feature/custom-reminder-offsets` (feature #2, ADR 0013) è pronto ma non ancora aperto/mergiato come PR. Nessun problema noto. Da fare: aprire la PR su dev; quando si vuole portare tutto in prod, workflow Prepare release (minor) → merge della release PR; aggiornare la lista comandi BotFather con `personalizza_orari`.
