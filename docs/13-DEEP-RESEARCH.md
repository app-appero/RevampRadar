# 13 — Deep Research & Concept Homepage

## Obiettivo

Un secondo livello di approfondimento, da usare soltanto sui prospect che
sembrano interessanti dopo Discovery + Audit + Opportunity Score. Non parte
mai automaticamente: si avvia a mano, azienda per azienda, con
**Approfondisci prospect**.

Il flusso esteso:

```text
Discovery → Audit → Opportunity Score → selezione manuale del prospect
  → Approfondisci prospect (Company Deep Research)
  → Company Brief
  → Design Brief
  → Concept Homepage HTML
  → Proposta commerciale
```

## Company Deep Research

Raccoglie solo dati realmente osservabili, con fonte:

- **Sito aziendale**: al massimo 5 pagine prioritarie (chi siamo, servizi,
  prodotti, contatti), scelte tra i link interni già noti dall'ultimo audit
  completato. Nessun crawling illimitato.
- **Presenza digitale**: estende l'Intelligence già esistente (tag OSM +
  link social/app trovati nell'HTML) in una vista per canale (sito,
  Instagram, Facebook, TikTok, YouTube, LinkedIn, App Store, Google Play):
  trovato/non trovato, URL, fonte. Nessuno scraping nuovo.
- **Social**: solo esistenza/URL dei profili già individuati. Nessuna
  osservazione su contenuti, engagement o performance: distinguere sempre
  osservazione pubblica, inferenza AI e dato verificato.
- **Articoli/fonti esterne**: astrazione provider pronta
  (`app/deep_research/`), ma senza un provider di ricerca a pagamento
  collegato di default — il campo resta vuoto finché non ne serve uno.

Stato: **Mai approfondita** · **Ricerca in corso** · **Completata** ·
**Parziale** (mancano sito, audit o pagine raggiungibili) · **Fallita** ·
**Da aggiornare** (un audit più recente è arrivato dopo l'ultima ricerca).

## Business Signals

Segnali economici (fatturato, dipendenti, anno di fondazione, forma
societaria, trend) con **valore, fonte, data, affidabilità**
(`verified`/`estimated`/`manual`/`unverified`). Nessun dato dedotto dalla
qualità del sito o stimato senza fonte. MVP a inserimento manuale
(`business_signals`, chiave `(azienda, tipo, periodo)`): nessun provider a
pagamento introdotto senza necessità concreta, coerente con AGENTS.md.
Un approfondimento non fallisce se questi dati mancano: restano "n/d".

## Company Brief

Sintesi automatica di quanto raccolto (mai un dato non presente nelle
fonti): cosa fa l'azienda, punti di forza emersi (solo se realmente
presenti nel testo delle pagine), presenza digitale, business signals,
problemi del sito già trovati dall'audit, possibile direzione della nuova
homepage, informazioni mancanti elencate esplicitamente. La sintesi
testuale (`what_it_does`, `homepage_direction`) può essere riscritta
dall'AI se configurata, sempre a partire dagli stessi fatti e con un
prompt che vieta esplicitamente di inventare numeri, nomi o anni; senza AI
resta un estratto deterministico delle pagine raccolte.

## Design Brief

Direzione visiva di partenza per il Concept: stile, palette, tipografia,
tone of voice, spaziature, border radius, trattamento immagini, CTA
principale. Derivata da un'euristica per categoria (hospitality, wellness,
professional, trade, retail, creative, default — `app/concept/design_brief.py`)
e, quando disponibile, dal colore di brand realmente dichiarato dal sito
(`meta theme-color`). Mai una palette casuale se un'identità è già
riconoscibile. Sempre modificabile a mano prima di rigenerare il concept;
un pulsante separato la riporta ai default.

## Concept Homepage HTML

**Genera concept homepage** produce una vera pagina HTML/CSS responsive
(desktop/mobile), non un'immagine. Sostituisce del tutto la vecchia
anteprima visiva indicativa (vedi ADR-015): quella applicava overlay
automatici a screenshot reali, questo genera contenuto vero da dati veri.

Regole:

- solo dati da Company Brief + Design Brief; nessun'invenzione di
  testimonianze, numeri, clienti, premi, anni o certificazioni;
- dove un contenuto manca: copy neutro o placeholder marcato internamente
  (badge "Concept dimostrativo" in testa alla pagina, testo "contenuto di
  esempio · da confermare" nei blocchi non verificati);
- sezioni adattive per settore (servizi vs prodotti; punti di forza solo
  se emersi davvero; presenza digitale solo per i canali trovati);
- niente screenshot del sito attuale nel concept: quelli restano la
  documentazione dello stato presente, il concept è la direzione futura;
- generatore deterministico (`app/concept/generator.py`); nessuna AI è
  necessaria per produrre l'HTML.

Ogni generazione crea una **nuova versione** (V1, V2, …) su filesystem
(`data/concepts/{company_id}/{concept_id}/index.html` + `styles.css`) e in
DB, senza cancellare le precedenti. `is_current` segue l'ultima
generazione; ogni versione resta apribile ed eliminabile singolarmente.

## Priorità locale

Una località di riferimento manuale in Impostazioni (mai GPS automatico)
permette di vedere la distanza indicativa dei prospect (haversine su
lat/lon già persistiti da OSM) e di ordinare/filtrare per distanza nella
lista aziende. Sotto una soglia configurabile, il Proposal Engine può
aggiungere una frase opzionale e modificabile sull'incontro di persona;
mai inserita di default, mai in automatico oltre la soglia.

## Proposal Engine

Quando un Concept corrente esiste, l'email può citare che è stata
preparata "anche una possibile direzione per la homepage" — solo se il
concept esiste davvero: un controllo scarta l'output AI se lo afferma
senza che sia vero (stesso pattern dei controlli già presenti su
prezzo/punteggi/orari). Non trasforma l'email in un audit tecnico.

## Non-goal

- generazione automatica del concept per ogni azienda scoperta;
- Deep Research avviata durante Discovery o Bulk Scanner;
- scraping aggressivo di piattaforme social o store;
- provider di dati economici a pagamento nell'MVP;
- invio automatico di email o pubblicazione del concept online.
