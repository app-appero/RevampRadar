# AGENTS.md

## Scopo

Questo file definisce le regole operative per qualsiasi agente AI che lavori sul repository RevampRadar.

## Fonte di verità

Prima di proporre o implementare modifiche, leggere almeno:

- README.md
- docs/00-PROJECT.md
- docs/01-PRODUCT.md
- docs/02-ARCHITECTURE.md
- docs/09-ROADMAP.md
- docs/10-TASKS.md
- docs/11-DECISIONS.md

Per task specifici leggere anche il documento relativo al modulo interessato.

La documentazione del repository prevale sulle supposizioni dell'agente.

## Principi vincolanti

1. RevampRadar nasce come applicazione personale desktop-first.
2. Il desktop è un client, non il core del prodotto.
3. La business logic deve vivere nel backend/core.
4. Stack desktop: Tauri 2 + React + TypeScript.
5. Stack backend: Python + FastAPI.
6. Database: PostgreSQL.
7. Docker è usato per lo sviluppo locale dei servizi.
8. Nessuna autenticazione o multi-tenancy nell'MVP.
9. Website Score e Opportunity Score sono concetti distinti.
10. Non usare AI per dati deterministici che possono essere misurati direttamente.
11. Evitare over-engineering.
12. Non implementare milestone future senza necessità tecnica esplicita.
13. Ogni nuova dipendenza deve avere una motivazione concreta.
14. Ogni modifica significativa deve rispettare la roadmap e i task documentati.
15. Le operazioni distruttive richiedono particolare cautela.

## Ruoli consigliati

### Claude
- architettura;
- analisi;
- pianificazione;
- review;
- ragionamento su casi limite;
- coerenza tra moduli.

### Codex
- implementazione;
- test;
- refactoring;
- bug fixing;
- task sul repository.

### Cursor
- sviluppo interattivo;
- debug;
- navigazione del codebase;
- piccole modifiche;
- review manuale;
- integrazione.

## Workflow consigliato

1. leggere documentazione;
2. identificare task e milestone;
3. analizzare lo stato corrente;
4. proporre un piano breve;
5. implementare solo lo scope richiesto;
6. eseguire test;
7. riportare file modificati;
8. segnalare eventuali deviazioni dalla documentazione.

## Regole Git

Branch suggeriti:

- `main`
- `develop`
- `feature/<nome-task>`
- `fix/<nome-bug>`

Evitare modifiche simultanee non coordinate sullo stesso modulo da più agenti.
