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

Postgres in Compose è esposto su `localhost:5433` per evitare conflitti con un PostgreSQL locale sulla 5432.

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

In M2 l'AI usa un client HTTP OpenAI-compatible (`OPENAI_BASE_URL` + `OPENAI_API_KEY`). Lo scoring deterministico non dipende dal provider.

Il primo provider di discovery è OpenStreetMap (Nominatim + Overpass): è strutturato, non richiede API key e copre il caso “Hotel — Sicilia”.

## ADR-011 — No over-engineering

Code, Redis, microservizi e infrastrutture complesse vengono introdotti solo quando servono.

M4 usa un thread pool in-process (`bulk_scan_concurrency`) per analizzare i siti di una discovery, con retry e ranking per Opportunity Score.

## ADR-012 — CRM su Opportunity, non su Company.status

Lo stato commerciale vive su `opportunities` (1:1 con company). `companies.status` resta il dato di discovery. Pipeline fissa da docs/08-CRM.md, senza automazioni marketing.

## ADR-013 — Proposal deterministica prima dell'AI

La proposta commerciale si genera da audit/finding/score già persistiti. L'AI può solo riscrivere i testi. Range, servizio consigliato e problemi prioritari restano deterministici. Non si inviano email.

## ADR-014 — Intelligence senza nuove API esterne

M7 usa solo dati già misurati (HTML, audit precedenti, tag OSM). Niente competitor crawl, ads o recensioni inventate. Il confronto storico è tra audit persistiti dello stesso website.

## ADR-015 — Anteprima visiva indicativa, non mockup di restyling

Gli screenshot extra sono catture reali (viewport desktop/mobile a quote diverse). L'anteprima "dopo" applica solo overlay deterministici (testo più leggibile, CTA, nascondere cookie banner) e va etichettata come indicativa. Non si generano immagini di restyling con AI: sarebbero inventate e fuorvianti in sede commerciale.
