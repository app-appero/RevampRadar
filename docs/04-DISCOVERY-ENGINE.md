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
- timestamp;
- avanzamento in % (località, Overpass, aziende persistite).

## Ricerca per provincia

- `province` accetta sigla (`BG`) o nome (`Bergamo`); senza città la località è
  «Provincia di Bergamo, Lombardia». Una sigla non sostituisce mai la località.
- Overpass interroga l'area del confine provinciale, non il bounding box.
- I risultati sono filtrati sulla provincia: poligono del confine, poi `addr:province`,
  poi elenco comuni. Esempio: «fiorista» in provincia di Bergamo non restituisce
  comuni di Brescia.
- Timeout Overpass sulla provincia: ricerca per comuni (admin_level 8) a gruppi
  (`OVERPASS_COMUNI_GROUP_SIZE`, default 12), con nuovo tentativo automatico
  (`OVERPASS_RETRY_ATTEMPTS`, default 2) e divisione dei gruppi che falliscono ancora.
  L'avanzamento mostra «ricerca per comuni N/M». Comuni senza risposta → stato `partial`.

## Stati

- queued
- running
- completed
- partial
- failed

## Non-goal iniziale

Non costruire un crawler general purpose del web.

Partire da fonti strutturate/API e mantenere il motore sostituibile.

Per l'arricchimento dei contatti, Google Places fornisce sito e telefono; se manca
l'email, è ammessa una ricerca limitata all'homepage e a un massimo di due pagine
di contatto sullo stesso dominio. Le richieste riusano lo scanner con protezione
SSRF e non seguono link verso altri domini.
