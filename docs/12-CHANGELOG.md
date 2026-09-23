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
- Proposal Engine: proposta commerciale da audit (summary, problemi, email, brief, range indicativo); AI opzionale solo sui testi.
- Intelligence: tech/social/OSM, confronto con audit precedente e freshness; senza nuove API esterne.
- Galleria screenshot: più viewport (inizio/contenuto/footer) e anteprima visiva indicativa, non un mockup di restyling.
- App signals: link App Store / Play trovati sulla homepage; niente recensioni store.
- Home: audit e discovery recenti più snapshot pipeline, per riprendere il lavoro senza perdere il filo.
- App Store listing: nome/rating da iTunes Lookup sui link già trovati; Play resta URL + package id, senza scraping.
- SaaS/demo: login, percorsi prodotto e widget rilevati sulla homepage, senza accedere a dashboard di terzi.
- Audit: tempi browser e, se c’è `PAGESPEED_API_KEY`, categorie PageSpeed visibili; lo score performance usa il punteggio PSI già salvato.
- Screenshot: clic per ingrandire in overlay; l’URL del sito si apre nel browser.
- Provider AI: Claude (default) o OpenAI, uno alla volta via `AI_PROVIDER`.
- Audit: barra di avanzamento in % su singolo sito, discovery OSM e analisi in batch.
- Impostazioni: nome, sito, piattaforme freelance e social in firma email; il range resta solo visibile all'operatore.
- Intelligence: recensioni App Store dal feed ufficiale Apple (sentiment e temi); Play resta URL + package id.
- Mappa: pin OSM colorati per Opportunity Score e gruppi geografici (k-means su lat/lon, senza probabilità di chiusura).
- Discovery: ricerca estesa fino a 200 risultati, include attività senza sito; elenco impaginato.
- Discovery: tag OSM visibili nel form, nei risultati e in anagrafica; se il settore non c’è, avviso e zero risultati (niente altri settori).
- Discovery: catalogo settori OSM ampliato (meccanico, gommista, mestieri, negozi); `start_date` e `opening_hours` se presenti su OSM.
- Discovery: menu settore e cascata regione → provincia → città, tutti opzionali (vuoto = Italia / tutti i settori).
- Agenda CRM: attività pianificate (`due_at`), calendario mensile, sezione in ritardo e completamento da desktop.
- Growth Potential Score: stima euristica (non ML) per le aziende senza sito, basata su categoria, concorrenza locale con sito già online, contattabilità e reputazione se nota; spiegabile con motivi/fattori come l'Opportunity Score.
- Proposal Engine "greenfield": proposta dedicata (servizio, range, email, brief) per chi non ha un sito, distinta da quella di refactor legata all'audit.
- Pipeline: filtro per segmento "da rifare" (con sito) / "da creare" (senza sito); il ranking usa il Growth Score come punteggio quando manca l'Opportunity Score, così i prospect senza sito non finiscono sempre in fondo.
- Discovery: telefono con fallback su `contact:mobile`/`mobile`; contatto social (WhatsApp/Facebook/Instagram) recuperato dai tag OSM e mostrato in anagrafica come alternativa quando telefono/email mancano.
- Scheda azienda: link "Cerca su Google Maps" per trovare a mano un contatto quando OSM non ne ha; niente API a pagamento, nessun dato salvato — è solo una ricerca che apri nel browser.
- Impostazioni: editor dei template email delle proposte (da rifare / da creare), con placeholder ({{nome_mittente}}, {{nome_attivita}}, {{luogo}}, {{dominio}}, {{firma}}) e pulsante per tornare al testo di default; il testo deterministico di partenza resta quello, personalizzabile senza toccare il codice.
- Impostazioni: chiavi AI (Claude/OpenAI) modificabili dall'app, salvate nel database e con priorità su quelle di `.env`; usate sia per l'analisi AI degli audit sia per le proposte.
- Proposte: alla generazione, se una chiave AI è configurata, un popup chiede se vuoi la versione arricchita con AI o quella di default; senza chiave si genera direttamente quella di default, senza chiedere.
- Prompt AI delle proposte: niente più gergo tecnico nell'email (spiega la conseguenza pratica, non i termini tecnici) e niente più proposte di durata/orario per una chiamata; un controllo lato codice scarta la risposta AI e usa il testo deterministico se lo ignora comunque.
- Discovery: risultati di una ricerca filtrabili per settore (utile con "tutti i settori", che mischia categorie diverse nello stesso elenco).
- Pipeline: filtro "Settore" ora è un menù a tendina con i settori realmente presenti in anagrafica, non più testo libero.

### Changed
- PageSpeed Insights è opzionale via `PAGESPEED_API_KEY`; Lighthouse nativo è rimandato (M1-014).
- L'analisi AI è un arricchimento: senza la chiave del provider scelto (`AI_PROVIDER=claude` o `openai`) l'audit tecnico e gli score deterministici restano validi.
- L'email di proposta si apre con chi sei e perché scrivi, senza prezzo.
- La mappa raggruppa per geografia; non predice chi accetterà.

### Decisions
- Tauri 2 + React + TypeScript;
- FastAPI + Python;
- PostgreSQL;
- Docker per sviluppo;
- nessuna autenticazione nell'MVP;
- discovery dopo la validazione dello scanner.
