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
1. **Promemoria privati per utente e per gruppo** — estendere con handler di subscribe/unsubscribe; il motore già itera su `subscriptions` (ADR 0008), quindi: INSERT con `origin='user'` + comandi Telegram. Non toccare il pruning.
2. **Orari di notifica personalizzabili per subscription** — il campo `reminder_offsets` è già per-riga; serve solo l'interfaccia (comandi) per impostarli.
3. Eventuale provider API strutturata in alternativa a fixturedownload (ADR 0007: nuova classe + entry nella factory + `CALENDAR_PROVIDER`).

**Operativo/monitoraggio:**
- La stagione 2026-27 inizia il **22 agosto 2026**: il primo reminder reale parte ~21 agosto. Verificare che arrivi sul canale (finora testati solo i comandi, non un reminder "live" in prod).
- Gli orari delle giornate lontane nel CSV sono placeholder (es. 00:00): si sistemano da soli col refresh giornaliero delle 02:00.
- Tentare ogni tanto la migrazione a VM A1.Flex (gratis, 6+ GB). Procedura: nuova VM → step DEPLOY.md → aggiornare secret `SSH_HOST` → rilanciare i deploy.

**Come lavorare con Matteo (vedi anche memoria persistente):**
- Stile consultivo: **proporre opzioni con trade-off** (AskUserQuestion) prima di decisioni di design/UX/infra; non applicare default in silenzio, anche su dettagli.
- **ADR prima del codice** per ogni decisione architetturale.
- I merge delle PR li fa **lui**; commit e push come comandi separati.
- **Niente `Co-Authored-By` nei commit né footer "Generated with" nelle PR.**
- Prima di dichiarare finito: `uv run ruff check && uv run ruff format --check && uv run mypy src && uv run pytest` tutti verdi.

**Stato al momento dell'handoff:** prod = v0.10.0 (release completa: deploy + tag + GitHub Release, tutto verificato); nessuna PR aperta, nessun problema noto.
