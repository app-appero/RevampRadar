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

## Server Overpass e nuovi tentativi

- Server provati in ordine: overpass-api.de, overpass.kumi.systems,
  overpass.private.coffee, lz4.overpass-api.de (`OVERPASS_URLS`). Si passa al
  successivo su errore di rete (es. «[Errno 101] Network is unreachable»), timeout o
  errore HTTP.
- Nella stessa ricerca si riparte dall'ultimo server che ha risposto; quelli
  irraggiungibili vanno in fondo e non vengono richiamati solo per confermare zero
  risultati.
- Se tutti i server sono irraggiungibili si riprova con attesa crescente
  (`OVERPASS_RETRY_ATTEMPTS`); poi la discovery è `failed` con un messaggio che elenca
  i server provati. Se la rete cade durante la ricerca per comuni, si tengono i
  risultati e la discovery è `partial`.
- `POST /discoveries/{id}/retry` (pulsante «Riprova ricerca») rimette in coda una
  discovery `failed` o `partial`, o rimasta `running`/`queued` da oltre 30 minuti
  (es. API riavviata durante un deploy), con gli stessi parametri. I risultati già
  trovati restano e contano nel totale.

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
