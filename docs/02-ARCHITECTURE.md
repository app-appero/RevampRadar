# 02 — Architecture

## Overview

RevampRadar utilizza un'architettura modulare composta da:

1. Desktop Application
2. API Backend
3. Scanner Engine
4. AI Analysis Engine
5. Opportunity Engine
6. Discovery Engine
7. Database
8. Background Jobs / Workers

## Desktop Application

Tecnologie:

- Tauri 2
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- TanStack Query
- React Router

Responsabilità:

- interfaccia;
- lancio analisi;
- visualizzazione risultati;
- gestione aziende;
- visualizzazione audit;
- CRM;
- configurazione;
- monitoraggio job.

Il client non deve contenere business logic critica.

## Backend

Tecnologie:

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

Responsabilità:

- API;
- business logic;
- orchestrazione scanner;
- scoring;
- AI;
- discovery;
- persistenza;
- integrazioni esterne.

## Database

PostgreSQL.

Entità principali:

- companies;
- websites;
- audits;
- audit_findings;
- screenshots;
- scores;
- discovery_runs;
- opportunities;
- contacts;
- activities;
- jobs.

## Scanner Engine

Responsabile dei dati deterministici:

- HTTP;
- HTTPS;
- redirect;
- response time;
- HTML;
- meta;
- heading;
- viewport;
- canonical;
- robots;
- sitemap;
- structured data;
- analytics;
- technology detection;
- broken links;
- performance.

## Browser Engine

Playwright viene utilizzato per:

- rendering reale;
- screenshot desktop;
- screenshot mobile;
- analisi DOM;
- controlli JS;
- responsive check.

## AI Analysis Engine

Input:

- screenshot;
- risultati tecnici;
- testo rilevante;
- struttura pagina;
- metadata.

Output strutturato:

- UI score;
- UX score;
- mobile score;
- conversion score;
- copy score;
- trust score;
- findings;
- recommendations.

## Opportunity Engine

Combina:

- qualità sito;
- gravità problemi;
- segnali aziendali;
- maturità digitale;
- reputazione;
- potenziale commerciale;
- miglioramenti possibili.

Produce:

- Website Score;
- Business Score;
- Opportunity Score;
- confidence;
- reasons;
- recommended service.

## Discovery Engine

Deve essere provider-agnostic.

Input:

- industry;
- geographic area;
- max results;
- filters.

Output normalizzato:

- company;
- website;
- category;
- location;
- contact metadata;
- business metadata.

## Worker Architecture

Per MVP è ammessa una gestione semplificata.

L'architettura deve comunque consentire in futuro code per:

- scansioni;
- Lighthouse;
- screenshot;
- discovery;
- enrichment;
- AI analysis.

## Sicurezza

- API key mai nel frontend;
- segreti via env/storage sicuro;
- input web esterni non affidabili;
- timeout e limiti sulle richieste;
- sanitizzazione dei dati;
- nessuna esecuzione arbitraria proveniente dai siti analizzati.

## Principio architetturale

Il desktop è un client.

Il backend/core deve poter essere riutilizzato in futuro da un frontend web senza riscrittura sostanziale.
