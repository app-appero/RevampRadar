# 12 — Changelog

## Unreleased

### Added
- definizione iniziale del prodotto RevampRadar;
- architettura desktop-first;
- roadmap M0–M8;
- separazione Website Score / Opportunity Score;
- definizione Single Website Analyzer come primo motore da validare;
- struttura documentazione per agenti AI;
- monorepo `apps/api` + `apps/desktop`;
- FastAPI con endpoint `/health`, logging, error handling e configurazione via env;
- PostgreSQL, SQLAlchemy, Alembic e Docker Compose;
- client React/Vite/Tauri 2 collegato allo stato del backend;
- Single Website Analyzer: audit HTTP/HTML/SEO, screenshot Playwright e finding tecnici.
- Opportunity Scoring: Website Score, Business Score preliminare, Opportunity Score spiegabile e AI opzionale.
- Company Discovery: ricerca per settore/località via OpenStreetMap, deduplica e anagrafica azienda.
- Bulk Scanner: analisi in batch dei siti di una discovery, retry, progress e ranking per Opportunity Score.
- CRM: opportunità 1:1 con azienda, pipeline, note, tag, preferiti, attività e filtri score/settore/località.

### Changed
- PageSpeed Insights è opzionale via `PAGESPEED_API_KEY`; Lighthouse nativo è rimandato (M1-014).
- L'analisi AI è un arricchimento: senza `OPENAI_API_KEY` l'audit tecnico e gli score deterministici restano validi.

### Decisions
- Tauri 2 + React + TypeScript;
- FastAPI + Python;
- PostgreSQL;
- Docker per sviluppo;
- nessuna autenticazione nell'MVP;
- discovery dopo la validazione dello scanner.
