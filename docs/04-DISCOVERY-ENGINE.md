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
- Errori transitori (rete, server sovraccarichi 429/502/503 e, fuori dalla ricerca
  per provincia, anche il timeout): stessa query ripetuta fino a
  `OVERPASS_RETRY_ATTEMPTS` (default 3) con attesa crescente (5 s, 10 s); poi la
  discovery è `failed` con un messaggio leggibile. In provincia il timeout passa alla
  ricerca per comuni. Se la rete cade durante la ricerca per comuni, si tengono i
  risultati e la discovery è `partial`.
- Richieste Overpass contemporanee limitate a `OVERPASS_MAX_CONCURRENCY` (default 2)
  per tutto il processo: più discovery lanciate insieme si mettono in fila invece di
  ricevere 429.
- Ogni avanzamento aggiorna `heartbeat_at`. Una discovery `queued`/`running` senza
  avanzamenti da oltre `DISCOVERY_STALE_MINUTES` (default 20) diventa `failed` con il
  motivo («Ricerca interrotta…», es. riavvio dell'API) quando si leggono, creano o
  rilanciano discovery.
- `POST /discoveries/{id}/retry` (pulsante «Riprova ricerca») rimette in coda una
  discovery `failed` o `partial` con gli stessi parametri. I risultati già trovati
  restano e contano nel totale.

## Deduplica nella discovery

Telefono, dominio del sito e nome+città non sono unici: fanno fondere un candidato
con un'azienda esistente solo se indicano una sola azienda. Se ne indicano più di una
la corrispondenza è ambigua e si crea una scheda nuova invece di andare in errore
(«Multiple rows were found», Romano di Lombardia). Sui domini condivisi (facebook.com,
instagram.com, sites.google.com, linktr.ee, booking.com…) il dominio non vale: conta
solo lo stesso URL.

## Contattabilità e resa

Con `require_contactable` un candidato è contattabile se ha sito, telefono, email o
un profilo social (`contact:instagram`, `contact:facebook`, WhatsApp, Telegram…), anche
quando il «sito» OSM è una pagina social. L'handle Instagram trovato su OSM va in
`instagram_handle`. Ogni discovery espone `stats`: candidati, tenuti, scartati per
motivo (`invalid`, `uncontactable`, `duplicate_in_run`, `over_max_results`), scarti lato
OSM (senza nome, altro settore, fuori provincia, senza sito in modalità standard) e
canali di contatto delle aziende tenute.

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
