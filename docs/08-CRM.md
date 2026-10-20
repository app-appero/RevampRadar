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
- sito;
- audit;
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
non sono già state verificate. La tabella mostra separatamente l'esito della
verifica (“Visto” / “Non visto”) dallo stato CRM. Una verifica completata che non
trova né sito né telefono sposta automaticamente l'opportunità in “Impossibili da
contattare”; errori tecnici e chiave mancante non contano come verifica.
I pulsanti mostrano il numero di aziende idonee e il progresso dell'operazione.
Durante un job sequenziale è possibile annullare: la chiamata già in corso termina,
ma non vengono avviate le aziende successive.
Il backend ricontrolla l'idoneità e non interpreta una selezione vuota come globale.
I job sono in memoria (come il recupero preesistente); gli audit e i dati recuperati
restano persistiti. Nessuna nuova dipendenza.

I filtri della Pipeline sono conservati nella sessione del client: aprire un
dettaglio azienda e tornare indietro, oppure ricaricare la pagina, ripristina
la ricerca precedente (testo, città, settore, stato, segmento e altri filtri).

Il menu Settore mostra solo categorie presenti con gli altri filtri attivi, con
conteggio aziende tra parentesi. Il backend raggruppa maiuscole/minuscole, spazi
e alias espliciti (es. barbiere/barbieri, hotel/albergo); il filtro usa lo stesso
gruppo e non una ricerca per sottostringa. I dati originali restano invariati.
Se cambiando gli altri filtri il settore selezionato non esiste piu, si torna
a Tutti per evitare una selezione senza risultati.
