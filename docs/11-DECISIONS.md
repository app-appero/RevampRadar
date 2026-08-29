# 11 — Architectural Decisions

## ADR-001 — Desktop-first

RevampRadar nasce come applicazione personale desktop.

Motivo:

- utilizzo singolo;
- niente infrastruttura SaaS iniziale;
- accesso diretto a scanner/browser locali;
- sviluppo più rapido.

## ADR-002 — Tauri 2

Client desktop basato su Tauri 2 + React + TypeScript.

## ADR-003 — Core separato

FastAPI contiene business logic e servizi.

Il frontend desktop non è il core.

## ADR-004 — PostgreSQL

Database relazionale principale.

## ADR-005 — Docker per sviluppo

Backend e database devono poter girare in Docker durante lo sviluppo.

Tauri può essere eseguito nativamente.

## ADR-006 — Single Analyzer prima della Discovery

Prima validare la qualità del motore di analisi.

Solo dopo automatizzare la scoperta di migliaia di aziende.

## ADR-007 — Deterministico prima dell'AI

Se un dato può essere misurato con codice, non deve essere demandato all'AI.

## ADR-008 — Score separati

Website Score e Opportunity Score devono rimanere separati.

## ADR-009 — No auth MVP

Nessun login nell'uso personale iniziale.

## ADR-010 — Provider abstraction

Discovery e AI devono poter cambiare provider senza riscrivere la business logic.

## ADR-011 — No over-engineering

Code, Redis, microservizi e infrastrutture complesse vengono introdotti solo quando servono.
