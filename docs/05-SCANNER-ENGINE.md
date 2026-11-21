# 05 — Scanner Engine

## Obiettivo

Produrre un audit riproducibile e strutturato di un sito.

## Input

- URL

## Output

- dati HTTP;
- dati HTML;
- dati SEO di base;
- dati performance;
- screenshot;
- finding;
- metadati audit.

## Controlli HTTP

- status code;
- HTTPS;
- redirect chain;
- response time;
- content type;
- page size.

## Controlli HTML

- title;
- meta description;
- H1;
- heading structure;
- canonical;
- viewport;
- lang;
- structured data;
- favicon.

## SEO tecnico

- robots.txt;
- sitemap.xml;
- canonical;
- indexability base;
- metadata;
- structured data.

## Tracking / Technology

- analytics;
- tag manager;
- pixel;
- CMS;
- framework;
- librerie principali.

## Link

- link interni;
- broken links base;
- CTA principali.

## Browser

Playwright deve produrre:

### Desktop
Viewport standard desktop: inizio pagina, contenuto (se la pagina è lunga) e footer.

### Mobile
Viewport smartphone: inizio pagina e contenuto.

### Anteprima visiva
Uno screenshot per viewport già catturato (desktop inizio/contenuto/footer, mobile inizio/contenuto), etichettato come indicativo: testo più leggibile, CTA visibile, banner cookie nascosti. Non è un mockup di restyling né una promessa pixel-perfect.

## Performance

Integrare Lighthouse/PageSpeed quando disponibile.

Metriche:

- Performance;
- Accessibility;
- Best Practices;
- SEO;
- Core Web Vitals disponibili.

## Findings

Ogni finding deve avere:

- category;
- severity;
- code;
- title;
- evidence;
- recommendation.

## Progresso scansione

Durante la scansione l'audit persiste `progress_percent` e `progress_label` a ogni passo (HTTP, HTML, SEO, screenshot, PageSpeed, AI, score). Lo stesso vale per discovery (Nominatim, Overpass, persistenza aziende) e per il bulk scan (siti completati sul totale). Il client mostra la percentuale; i finding restano visibili a scansione conclusa.

## Modalità gratuita (free_only)

`POST /audits` con `free_only=true` (default per le chiamate automatiche, bulk scan e
analisi in blocco) salta analisi AI e PageSpeed: nessuna chiamata a OpenAI, Anthropic o
Google. HTTP, HTML, SEO, screenshot locali e score deterministici restano invariati; la
risposta riporta `ai_status: skipped_free_mode`. L'analisi manuale dal desktop usa
`free_only=false`.

Controlli locali (anche in modalità completa), elencati nell'audit in `checks` con esito
`ok`, `problem` o `not_checked`:

- stato HTTP della home;
- certificato TLS: se non è valido la pagina si legge comunque (protezione SSRF attiva),
  `tls_valid=false` e finding `TLS_INVALID_CERTIFICATE`, senza bonus HTTPS nel trust;
- meta viewport e title (vuoto = assente);
- scorrimento orizzontale a 390px, misurato nella cattura mobile di Playwright
  (`MOBILE_HORIZONTAL_OVERFLOW` oltre 8px);
- anno del copyright nel footer (`HTML_STALE_FOOTER_YEAR` se fermo da 2 anni o più);
- fino a `BROKEN_LINKS_MAX` (default 10) link interni della home, HEAD con ripiego GET
  (`LINKS_BROKEN` per 4xx/5xx o pagine irraggiungibili).

## Severità

- info
- low
- medium
- high
- critical

## Resilienza

Gestire:

- timeout;
- DNS error;
- SSL error;
- redirect loop;
- anti-bot;
- pagine non HTML;
- sito offline;
- rendering incompleto.

## Principio

L'AI non deve calcolare ciò che può essere misurato deterministicamente.
