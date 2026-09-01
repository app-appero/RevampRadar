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
