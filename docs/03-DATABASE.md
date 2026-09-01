# 03 — Database

## Obiettivo

Definire un modello dati semplice ma estendibile.

## Entità iniziali

### Company

Campi suggeriti:

- id
- name
- category
- city
- region
- country
- latitude
- longitude
- website_url
- phone
- email
- source
- external_id
- status
- created_at
- updated_at

### Website

- id
- company_id
- url
- normalized_url
- domain
- is_active
- created_at
- updated_at

### Audit

- id
- website_id
- status
- started_at
- completed_at
- scanner_version
- created_at

### AuditFinding

- id
- audit_id
- category
- severity
- code
- title
- description
- evidence
- recommendation
- source_type

### Screenshot

- id
- audit_id
- device
- viewport_width
- viewport_height
- file_path
- created_at

### WebsiteScore

- id
- audit_id
- technical_score
- ui_score
- ux_score
- mobile_score
- conversion_score
- seo_score
- overall_score
- explanation

### OpportunityScore

- id
- company_id
- audit_id
- website_score
- business_score
- opportunity_score
- confidence
- priority
- explanation
- recommended_service

### DiscoveryRun

- id
- industry
- location
- max_results
- provider
- status
- total_found
- started_at
- completed_at

### Opportunity

- id
- company_id
- status
- priority
- notes
- created_at
- updated_at

### SenderProfile

Profilo singolo dell'operatore (nessuna auth):

- display_name
- intro
- website_url
- freelancer_links
- social_links

Usato in firma email. Il range proposta resta sui record `proposals`, non va nel testo inviato al prospect.

### Contact

- id
- company_id
- name
- role
- email
- phone
- linkedin_url

### Activity

- id
- company_id
- type
- note
- occurred_at

## Vincoli

- dominio normalizzato per deduplica;
- audit storico, non sovrascrivere i precedenti;
- score collegati alla specifica versione di audit;
- stati CRM separati dai dati tecnici.

## Migrazioni

Usare Alembic.

Ogni modifica allo schema deve avere una migration versionata.
