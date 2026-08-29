# 04 — Discovery Engine

## Obiettivo

Trovare aziende reali partendo da criteri commerciali.

## Input

- settore;
- località;
- raggio opzionale;
- max risultati;
- filtri opzionali.

## Output normalizzato

- nome azienda;
- categoria;
- località;
- sito;
- telefono;
- rating;
- numero recensioni;
- source;
- external_id.

## Provider abstraction

Definire un'interfaccia comune, ad esempio:

- search_businesses()
- get_business_details()
- normalize_result()

La business logic non deve dipendere da un provider specifico.

## Normalizzazione

Gestire:

- URL;
- dominio;
- telefono;
- località;
- categorie;
- duplicati.

## Deduplica

Chiavi possibili:

1. dominio;
2. external_id provider;
3. nome + città;
4. telefono.

## Discovery Run

Ogni ricerca deve essere persistita con:

- parametri;
- provider;
- stato;
- numero risultati;
- errori;
- timestamp.

## Stati

- queued
- running
- completed
- partial
- failed

## Non-goal iniziale

Non costruire un crawler general purpose del web.

Partire da fonti strutturate/API e mantenere il motore sostituibile.
