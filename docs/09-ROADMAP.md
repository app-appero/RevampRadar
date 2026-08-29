# 09 — Roadmap

## M0 — Foundation

Obiettivo: creare base tecnica stabile.

Deliverable:

- repository;
- monorepo;
- React/TypeScript;
- Tauri 2;
- FastAPI;
- PostgreSQL;
- SQLAlchemy;
- Alembic;
- Docker Compose;
- health endpoint;
- collegamento desktop → API;
- configurazione;
- logging;
- test;
- lint/format.

Definition of Done:

L'app desktop parte, il backend risponde e il database è raggiungibile.

---

## M1 — Single Website Analyzer

Obiettivo: validare il motore centrale su un singolo URL.

Deliverable:

- input URL;
- validazione;
- creazione audit;
- scanner HTTP/HTML;
- Playwright desktop/mobile;
- screenshot;
- Lighthouse/PageSpeed;
- finding tecnici;
- pagina risultato audit.

Definition of Done:

Inserendo un URL reale, RevampRadar produce un audit tecnico completo e consultabile.

---

## M2 — Opportunity Scoring Prototype

Obiettivo: trasformare l'audit in valutazione utile commercialmente.

Deliverable:

- AI analysis strutturata;
- Website Score;
- Business Score preliminare;
- Opportunity Score;
- priority;
- confidence;
- top reasons;
- recommended service.

Definition of Done:

Dato un sito, il sistema spiega se e perché rappresenta un'opportunità.

---

## M3 — Company Discovery

Obiettivo: trovare automaticamente aziende reali.

Deliverable:

- DiscoveryRun;
- provider abstraction;
- primo provider;
- normalizzazione;
- deduplica;
- Companies list;
- company detail base.

Definition of Done:

La ricerca “Hotel — Sicilia” restituisce aziende persistite con relativi siti.

---

## M4 — Bulk Scanner

Obiettivo: applicare il motore M1/M2 ai risultati discovery.

Deliverable:

- queue/job;
- scansione multipla;
- retry;
- progress;
- error handling;
- ranking per Opportunity Score.

Definition of Done:

Una discovery può essere analizzata in batch e ordinata per opportunità.

---

## M5 — Dashboard & CRM

Obiettivo: rendere operativa la gestione commerciale.

Deliverable:

- dashboard;
- filtri;
- pipeline;
- note;
- tags;
- favorites;
- attività;
- shortlist.

---

## M6 — Proposal Engine

Obiettivo: trasformare analisi e finding in proposta commerciale.

Deliverable:

- summary;
- problemi prioritari;
- servizio consigliato;
- strategia;
- email personalizzata;
- brief;
- range progetto indicativo.

---

## M7 — Advanced Intelligence

Possibili estensioni:

- social signals;
- recensioni;
- advertising signals;
- competitor analysis;
- historical changes;
- technology aging;
- enrichment;
- monitoring.

---

## M8 — App / SaaS Analysis

Solo dopo validazione sui siti web:

- App Store;
- Google Play;
- review sentiment;
- feature request mining;
- SaaS pubblici;
- piattaforme con demo pubbliche.
