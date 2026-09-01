# RevampRadar

RevampRadar è un'applicazione desktop personale progettata per individuare aziende con una presenza digitale migliorabile e trasformarle in opportunità commerciali qualificate.

## Obiettivo

Il prodotto deve permettere di:

1. analizzare un singolo sito;
2. valutarne qualità tecnica, UX/UI e potenziale di conversione;
3. calcolare un Website Score;
4. calcolare un Opportunity Score separato;
5. individuare aziende interessanti tramite discovery;
6. ordinare i prospect per priorità commerciale;
7. gestire i lead in una pipeline CRM;
8. generare successivamente proposte commerciali personalizzate.

## Struttura del repository

```text
apps/
  api/         FastAPI, SQLAlchemy, Alembic
  desktop/     Tauri 2 + React + TypeScript
docs/          Fonte di verità prodotto e architettura
prompts/       Prompt operativi per gli agenti
```

## Avvio locale

Prerequisiti: Docker, Python 3.12+, Node.js 22+, Rust (solo per la shell Tauri).

1. Copiare `.env.example` in `.env`.
2. Avviare database e API:

```bash
docker compose up --build
```

Postgres è esposto su `localhost:5433` per non collidere con un'installazione locale sulla 5432.

3. Verificare il backend:

```bash
curl http://localhost:8000/health
```

4. Avviare il frontend (browser o Vite; Tauri richiede Rust):

```bash
cd apps/desktop
cp .env.example .env
npm install
npm run dev
```

La UI è su `http://localhost:1420`. In home analizzi un URL e riprendi audit e discovery recenti. A scansione completata vedi Website Score, Opportunity Score, screenshot, metriche di performance e Intelligence (social, App Store, SaaS/demo). Da **Discovery** cerchi aziende e lanci l’analisi in batch. Da **Mappa** vedi i pin OSM e i gruppi geografici. Da **Pipeline** gestisci stati CRM, shortlist, note e attività. Da un audit completato puoi **generare una proposta**.

L'analisi qualitativa AI è opzionale. In `.env` imposta `AI_PROVIDER=claude` (default) o `openai`, e la chiave corrispondente (`ANTHROPIC_API_KEY` o `OPENAI_API_KEY`). Senza chiave, gli score deterministici vengono calcolati lo stesso.

Per la finestra nativa, dopo aver installato Rust:

```bash
cd apps/desktop
npm run tauri dev
```

API nativa (senza container `api`), con solo Postgres in Docker:

```bash
docker compose up db -d
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Test e lint

```bash
cd apps/api
pytest
ruff check .

cd ../desktop
npm run lint
```

## Stack

### Desktop
- Tauri 2
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- TanStack Query
- React Router

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

### Database
- PostgreSQL

### Scanner
- Playwright
- HTTPX
- BeautifulSoup
- Lighthouse
- PageSpeed Insights

### Dev
- Docker
- Docker Compose
- Git
- GitHub
- pytest
- ESLint
- Prettier

## Roadmap

- M0 — Foundation
- M1 — Single Website Analyzer
- M2 — Opportunity Scoring Prototype
- M3 — Company Discovery
- M4 — Bulk Scanner
- M5 — Dashboard & CRM
- M6 — Proposal Engine
- M7 — Advanced Intelligence
- M8 — App / SaaS Analysis

## Documentazione

La cartella `docs/` rappresenta la fonte di verità funzionale e architetturale del progetto.

Gli agenti AI devono leggere `AGENTS.md` e i documenti rilevanti prima di modificare il codice.
