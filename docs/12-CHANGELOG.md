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
- client React/Vite/Tauri 2 collegato allo stato del backend.

### Decisions
- Tauri 2 + React + TypeScript;
- FastAPI + Python;
- PostgreSQL;
- Docker per sviluppo;
- nessuna autenticazione nell'MVP;
- discovery dopo la validazione dello scanner.
