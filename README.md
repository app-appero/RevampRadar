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
