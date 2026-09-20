# ADR 0037: Rilicenziamento in AGPL-3.0-or-later

- Status: accepted
- Date: 2026-09-20

## Context

Il progetto nasce sotto **GPL-3.0-or-later**: `COPYING` contiene il testo
integrale della GPLv3, `pyproject.toml` dichiara `license = "GPL-3.0-or-later"`
e il README rimanda a `COPYING`. La scelta non è mai stata documentata in una
ADR, quindi l'intento dietro di essa non era ricostruibile se non a posteriori.

L'intento, esplicitato ora, è **reciprocità**: chi costruisce sopra questo bot
restituisce le proprie modifiche. La GPLv3 non lo ottiene in questo contesto.

Il bot è un **servizio di rete**: gira su una VM, e gli utenti ci interagiscono
via Telegram senza mai ricevere una copia del programma. Il copyleft della
GPLv3 scatta sulla **distribuzione** dell'opera, non sulla sua esecuzione:
chiunque può forkare il repository, modificarlo, deployare il proprio bot e non
pubblicare nulla, restando pienamente conforme alla licenza. È la *ASP
loophole*, ed è esattamente lo scenario realistico per un bot Telegram — il
codice non viene ridistribuito, viene fatto girare.

L'unico punto in cui gli obblighi GPL scattano davvero oggi è l'immagine
pubblicata su GHCR, che **è** distribuzione. Gli obblighi risultano soddisfatti
solo di fatto (il repository è pubblico), non per dichiarazione: il `Dockerfile`
non espone alcuna label OCI che colleghi l'immagine al suo sorgente.

**Compatibilità delle dipendenze** — nessun vincolo contrario:

| Dipendenza | Licenza | Nota |
| --- | --- | --- |
| python-telegram-bot 22.8 | LGPL-3.0-only | combinabile con (A)GPLv3; l'opera risultante resta (A)GPLv3 |
| pydantic-settings, pydantic-core | MIT | permissiva |
| httpx | BSD-3-Clause | permissiva |

La AGPLv3 è esplicitamente compatibile con LGPLv3 e con GPLv3 (GPLv3 §13), per
cui il salto non tocca nulla a valle.

**Titolarità**: `git log` riporta come autori umani soltanto Matteo Pelliccione
(due indirizzi email personali); i restanti commit sono di `github-actions[bot]`
e `dependabot[bot]`, che non apportano contributi originali soggetti a diritto
d'autore. Il rilicenziamento è quindi unilaterale: nessun CLA, nessun consenso
di terzi da raccogliere.

Le alternative considerate:

- **restare su GPL-3.0-or-later** — coerente se i fork self-hosted non sono un
  problema (anzi: abbassano l'attrito per chi vuole solo il proprio bot), ma
  non realizza l'intento di reciprocità dichiarato sopra;
- **MIT o Apache-2.0** — direzione opposta, massimizza il riuso di parti isolate
  (`reminders/planner.py`, il provider calendario) rinunciando alla
  reciprocità. Contraddice una scelta già presa, non la corregge.

## Decision

**Il progetto passa a AGPL-3.0-or-later.** La AGPLv3 è la GPLv3 più il §13, che
estende l'obbligo di offrire il sorgente a chi interagisce con una versione
modificata **attraverso una rete**: è precisamente il buco descritto sopra.

Il changeset:

- `COPYING`: testo integrale della GNU Affero General Public License v3.0, in
  sostituzione di quello GPLv3. Il file mantiene il nome attuale (GitHub
  riconosce `COPYING` come file di licenza; rinominarlo sarebbe cosmetico).
- `pyproject.toml`: `license = "AGPL-3.0-or-later"`, più
  `license-files = ["COPYING"]` (PEP 639) — finora assente, con l'effetto che
  il file di licenza non finiva nei metadati del pacchetto.
- `README.md`: sezione License aggiornata e **nota di copyright esplicita**
  (`Copyright (C) 2026 Matteo Pelliccione`), oggi assente ovunque nel
  repository nonostante la sezione "How to Apply" della licenza stessa la
  richieda.
- `Dockerfile`: label OCI `org.opencontainers.image.source` e
  `org.opencontainers.image.licenses`, così che l'immagine pubblicata dichiari
  da sé dove trovare il proprio sorgente.
- **Visibilità per l'utente finale**: il §13 richiede che l'offerta di sorgente
  raggiunga chi usa il servizio. Il link al repository viene esposto **in
  `/help`**, non con un comando `/licenza` dedicato: un comando in più per un
  adempimento legale peserebbe sulla superficie del bot senza che nessuno lo
  cerchi, mentre `/help` è il punto in cui un utente curioso guarda comunque.
  Il testo segue ADR 0018 (italiano, HTML parse mode, informazione prima della
  battuta).

Il rilicenziamento **non è retroattivo**: i tag già pubblicati restano
disponibili sotto GPL-3.0-or-later, e chi li ha già ottenuti conserva quei
diritti. La AGPL si applica dal commit di rilicenziamento in avanti.

## Consequences

- Chi deploya una versione **modificata** del bot deve offrirne il sorgente ai
  propri utenti. Chi deploya una copia **non modificata** non ha obblighi nuovi:
  il §13 si attiva sulle modifiche.
- Chi forka per uso privato senza esporre il bot a nessuno non è toccato: la
  AGPL non impone di pubblicare, impone di offrire il sorgente a chi *usa* il
  servizio.
- La AGPL è nella blocklist di molte policy aziendali di terze parti. È un costo
  reale in astratto e irrilevante qui: il progetto non punta all'adozione
  enterprise.
- Il §13 si applica a "chi interagisce con il programma attraverso una rete".
  Nel caso di un bot Telegram l'interazione passa per i server di Telegram,
  quindi esiste un grado di indirezione che la lettera della licenza non
  contempla esplicitamente. L'esposizione del link in `/help` risolve la
  questione in via pratica a prescindere da come la si interpreti.
- Ogni nuovo contributo esterno (PR) arriva sotto AGPL-3.0-or-later per
  inbound=outbound. Se in futuro si volesse tornare a una licenza più
  permissiva servirebbe il consenso di ogni contributore, che oggi — con un solo
  autore — non è ancora un costo.
- La riga `license` in `pyproject.toml` resta un'espressione SPDX (PEP 639),
  senza classifier `License ::` corrispondente: è la forma corretta e non va
  "completata" con i classifier deprecati.
