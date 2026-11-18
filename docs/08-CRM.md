# 08 — CRM

## Obiettivo

Gestire le opportunità senza trasformare RevampRadar in un CRM generalista.

## Pipeline iniziale

- Discovered
- Analyzed
- Qualified
- Shortlisted
- To Contact
- Contacted
- Replied
- Meeting
- Proposal
- Won
- Lost
- Impossibili da contattare

## Funzioni

- cambio stato;
- note;
- tag;
- preferiti;
- attività;
- attività pianificate (richiami, meeting) con data/ora;
- agenda con calendario e completamento;
- storico;
- contatti;
- filtro per score;
- filtro per settore/località.

## Company Detail

Mostrare:

- dati azienda;
- telefono ed email modificabili, con aggiornamento della verifica contatti;
- sito;
- audit;
- storico comparativo degli audit, ordinato dal più recente, con tutti gli score e andamento Website/Opportunity Score;
- screenshot;
- score;
- finding;
- ragioni Opportunity Score;
- stato CRM;
- note;
- attività.

## Non-goal

Nell'MVP non servono:

- automazioni marketing;
- campagne email massive;
- pipeline configurabili complesse;
- team;
- permessi;
- forecasting commerciale avanzato.

## Operazioni sulla selezione della Pipeline

Le caselle su ogni riga e “Seleziona tutti i risultati della ricerca” selezionano
solo le aziende restituite dai filtri correnti. Cambiare filtri azzera la selezione.
“Analizza siti” avvia audit sequenziali per le selezionate con sito;
“Recupera solo non visti” cerca su Google Places solo le selezionate senza sito che
non sono già state verificate; avviando il recupero, la selezione viene ridotta a
queste aziende e le righe già viste vengono deselezionate. La tabella mostra
separatamente l'esito della verifica dallo stato CRM: “Non visto”, “Visto” (email
presente), “Visto - senza email” (numero presente) o “Visto - senza contatti”
(né numero né email). Una verifica completata senza
sito, email e telefono sposta automaticamente l'opportunità in “Impossibili da
contattare”, aggiunge il tag “nd” e una nota esplicativa; errori tecnici e chiave
mancante non contano come verifica.
I pulsanti mostrano il numero di aziende idonee e il progresso dell'operazione.
Durante un job sequenziale è possibile annullare: la chiamata già in corso termina,
ma non vengono avviate le aziende successive.
Il backend ricontrolla l'idoneità e non interpreta una selezione vuota come globale.
I job sono in memoria (come il recupero preesistente); gli audit e i dati recuperati
restano persistiti. Nessuna nuova dipendenza.

I contatti possono essere inseriti o corretti manualmente anche dalla pagina
azienda e, dopo un audit completato, dalla pagina del risultato. Salvando almeno
un telefono o un'email l'azienda risulta verificata: email presente = “Visto”,
solo telefono = “Visto - senza email”. La tabella comparativa include ogni audit
collegato all'azienda e mantiene il più recente in cima.

I filtri della Pipeline sono conservati nella sessione del client: aprire un
dettaglio azienda e tornare indietro, oppure ricaricare la pagina, ripristina
la ricerca precedente (testo, città, settore, stato, segmento e altri filtri).

Il menu Settore mostra solo categorie presenti con gli altri filtri attivi, con
conteggio aziende tra parentesi. Il backend raggruppa maiuscole/minuscole, spazi
e alias espliciti (es. barbiere/barbieri, hotel/albergo); il filtro usa lo stesso
gruppo e non una ricerca per sottostringa. I dati originali restano invariati.
Se cambiando gli altri filtri il settore selezionato non esiste piu, si torna
a Tutti per evitare una selezione senza risultati.

## Inserimento manuale, senza analisi

`POST /companies` crea un'azienda e la sua Opportunity nella stessa transazione.
Il salvataggio valida solo i dati inviati e li persiste: non avvia audit, scanner,
screenshot, richieste al sito, AI, PageSpeed, Places, geocodifica, Discovery,
arricchimenti o proposte. Lo stato commerciale sta sull'Opportunity. Non vengono
generati audit né punteggi.

Il nome è obbligatorio. Sito, email, telefono, social, settore, città, provincia,
regione, fonte, note e tag sono facoltativi. La provincia non ha una colonna
propria: resta in `extra.province`. I campi vuoti non vengono inventati.

Se la corrispondenza è certa si restituisce la scheda già presente (200). Se è
ambigua si risponde 409 con i candidati e non si crea né si fonde nulla. Il nome
da solo non identifica un'azienda. Un dominio condiviso, un numero centralizzato
o un'email comune non uniscono sedi o attività diverse. Una richiesta ripetuta
con gli stessi dati è idempotente.

In Pipeline il pulsante «Aggiungi azienda» apre il modulo e «Salva azienda»
chiama solo questo endpoint. «Analizza sito» resta un'azione distinta.

### Anteprima e import con creazione

`POST /opportunities/import` non cambia: aggiorna solo aziende già presenti.

`POST /companies/import/preview` non scrive sul database e classifica ogni riga
come `new`, `existing`, `update`, `ambiguous`, `invalid` o `id_not_found`.
`POST /companies/import` crea le mancanti solo se `create_missing` è `true`,
riusando lo stesso servizio. Gli ID nuovi li genera il backend. Per ogni riga
tornano il `ref` del chiamante, `company_id`, `opportunity_id`, l'esito e
l'eventuale errore.

Un `company_id` inesistente non basta a creare una scheda: serve un'altra
corrispondenza certa, altrimenti l'esito è `id_not_found`. Valori vuoti non
cancellano dati. Note, tag e social non si duplicano. Stati più avanzati di
quello richiesto, e le esclusioni (`lost`, `uncontactable`, `not_now`), non
vengono retrocessi.

### Storico contatti già avvenuti

Gli eventi storici sono attività, non invii. I tipi sono `email_sent`,
`dm_sent` (primo DM solo testo) e `concept_sent` (distinto dal primo DM).
Canale, mittente, destinatario, lotto (`batch_id`) e riferimento esterno
(`external_ref`, univoco) stanno sull'attività. Se si conosce solo la data si
usa `occurred_on` (`YYYY-MM-DD`) e `occurred_at` resta vuoto: non si inventa
un orario. Un timestamp va in `occurred_at` e deve avere il fuso.

Registrare l'evento non spedisce messaggi e non equivale a consegna, lettura o
risposta. Se lo stato è già successivo a `contacted`, o è un'esclusione, resta
com'è: l'invio è comunque registrato e una nota segnala il conflitto da
verificare. Lo stesso `external_ref` al reimport non duplica l'evento.

Esempio di creazione:

```json
{
  "name": "Bar Rossi",
  "website_url": "https://barrossi.example",
  "email": "sala@barrossi.example",
  "phone": "+39 091 000111",
  "social_links": [{"label": "Instagram", "url": "https://instagram.com/barrossi"}],
  "category": "bar",
  "city": "Palermo",
  "province": "Palermo",
  "region": "Sicilia",
  "source": "contatto",
  "status": "to_contact",
  "notes": ["Già sentita a voce"],
  "tags": ["lotto2"]
}
```

Esempio di anteprima:

```json
{
  "create_missing": true,
  "rows": [
    {
      "ref": "riga-01",
      "name": "Nuova Bottega",
      "city": "Roma",
      "events": [
        {
          "external_ref": "lotto2-20261116-0800:email:riga-01",
          "kind": "email_sent",
          "channel": "email",
          "sender": "io@example.com",
          "recipient": "bottega@example.com",
          "batch_id": "lotto2-20261116-0800",
          "occurred_on": "2026-11-16"
        }
      ]
    }
  ]
}
```

La risposta dell'import, una riga per esito, ha questa forma:

```json
{
  "create_missing": true,
  "dry_run": false,
  "rows": [
    {
      "ref": "riga-01",
      "outcome": "created",
      "company_id": "00000000-0000-4000-8000-000000000001",
      "opportunity_id": "00000000-0000-4000-8000-000000000002",
      "error": null,
      "warnings": [],
      "changes": ["name", "city", "events"],
      "candidates": [],
      "events": [
        {"external_ref": "lotto2-20261116-0800:email:riga-01", "outcome": "recorded", "error": null}
      ]
    }
  ]
}
```

Gli UUID qui sopra sono segnaposto: quelli veri li assegna il backend al momento
della creazione. Il lotto `lotto2-20261116-0800` è il caso da supportare (email
e primi DM, senza concept Instagram), ma il file di quel lotto non va importato
dai test né inventato.

## API: ricerca, note e controllo contatti

- `GET /opportunities?q=…` cerca nel nome azienda; `search` è un alias di `q`
  (se presenti entrambi vale `q`). Vale anche per export e faccette settore.
  `?tag=lotto3-20261123` filtra per nome esatto del tag (maiuscole indifferenti).
  `?domain=2-emme.com` filtra per dominio esatto del sito (`www.` ignorato, accetta
  anche un URL; niente sottodomini né corrispondenze parziali): da usare prima di
  `POST /companies` per non creare duplicati.
- Paginazione: `limit` (1-1000) e `offset`. L'header `X-Total-Count` riporta il
  totale filtrato, non la dimensione della pagina; una pagina più corta di `limit`
  è l'ultima. Senza `limit` si ricevono tutti i record (uso del desktop). L'ordine
  è stabile (preferiti, punteggio, aggiornamento, id) così le pagine non si
  sovrappongono anche quando molti record hanno lo stesso `updated_at`.
- `GET /opportunities/{id}/notes` restituisce le note dalla più recente.
- `POST /opportunities/{id}/notes` vuole `{"body": "testo"}`. `content`, `text` o
  `note` restituiscono 422 con l'indicazione del campo corretto.
- `DELETE /opportunities/{id}/tags/{tag}` toglie un solo tag da quell'opportunità;
  `{tag}` è l'id o il nome (es. `lotto3-20261123`). 404 se il tag non c'è.
- `POST /opportunities/contact-status` con `{"emails": [...]}` restituisce per ogni
  email stato CRM, `contacted_on` (ultimo contatto) ed evidenze. Un'email si collega
  all'azienda tramite email anagrafica, destinatario di un'attività o testo di
  note/attività. Già contattata = stato contacted o successivo, invio registrato
  (`email_sent`, `dm_sent`, `concept_sent`, attività email svolta) o tag di invio
  (segmento «inviato/inviata», es. `lotto2-20261116-inviato`, più eventuali
  `contacted_tags`). Va usato prima di inviare bozze esterne (Aruba). Sola lettura.

