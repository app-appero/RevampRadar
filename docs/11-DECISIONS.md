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

In M2 l'AI usa un provider selezionabile (`AI_PROVIDER=claude` default, oppure `openai`). Claude parla con l'API Anthropic (`ANTHROPIC_API_KEY`); OpenAI resta sul client HTTP compatible (`OPENAI_BASE_URL` + `OPENAI_API_KEY`). Lo scoring deterministico non dipende dal provider.

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

## ADR-016 — M8 parte dai link store già sul sito

Il primo passo App/SaaS è rilevare link App Store e Play sulla homepage già scaricata. Niente scraping store, recensioni o rating inventati. Listing e sentiment restano dopo la validazione del flusso siti.

## ADR-017 — Listing App Store da iTunes Lookup, recensioni dal feed Apple

Se la homepage ha un link App Store con id numerico, Intelligence chiama l'API pubblica iTunes Lookup (nome, versione, rating medio, numero voti) e, se disponibile, il feed ufficiale RSS/JSON delle recensioni recenti (`customerreviews`). Sentiment e temi (crash, pagamenti, richieste) si calcolano solo su quei testi. Play Store resta solo URL e package id dal query string: non c'è API ufficiale e non facciamo scraping.

## ADR-018 — SaaS/demo solo da segnali on-site

M8-006 rileva login, percorsi prodotto (`/pricing`, `/demo`, `/app`…), CTA demo/trial e widget noti (Stripe, Intercom, Calendly, HubSpot, Zendesk, Crisp) sulla homepage già scaricata. Non si entra in dashboard di terzi e non si inventano recensioni o feature request.

## ADR-019 — Range interno, firma da impostazioni

Il range progetto resta deterministico e visibile solo all'operatore. L'email al prospect non contiene prezzi. Presentazione, sito, piattaforme freelance e social arrivano da un profilo impostazioni unico (app personale, senza login). L'AI può riscrivere il tono ma non reinserire il prezzo né inventare contatti.

## ADR-020 — Mappa descrittiva, clustering solo geografico

La mappa usa lat/lon persistiti da OpenStreetMap (nodo o `center` Overpass). I punti si colorano con l'Opportunity Score già calcolato. Il clustering è k-means non supervisionato sulle sole coordinate, in Python senza dipendenze ML: descrive gruppi spaziali (città, categoria, score medio, quota app). Non stima la probabilità che un prospect accetti. Le aziende scoperte prima della persistenza coordinate restano senza pin finché non si rilancia una discovery OSM.

