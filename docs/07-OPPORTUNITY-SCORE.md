# 07 — Opportunity Score

## Obiettivo

Separare qualità del sito e potenziale commerciale.

## Website Score

Misura la qualità digitale del sito.

Componenti candidate:

- technical;
- performance;
- mobile;
- UX;
- UI;
- SEO;
- conversion;
- trust.

Scala:

0–100

Score alto = sito buono.

## Business Score

Misura segnali commerciali disponibili.

Esempi:

- attività apparentemente attiva;
- rating;
- volume recensioni;
- settore;
- presenza digitale;
- segnali di investimento;
- dimensione percepibile;
- potenziale valore progetto.

## Opportunity Score

Score alto = prospect interessante.

Il modello deve considerare che:

- un sito molto scarso può essere un'opportunità;
- ma un'attività inattiva o piccolissima può avere basso potenziale;
- un'azienda forte con sito mediocre può avere altissimo potenziale.

## Formula iniziale

La formula definitiva va validata empiricamente.

Bozza:

- website gap: 35%
- business potential: 30%
- solvable problems: 15%
- conversion opportunity: 10%
- digital activity: 10%

## Priority

- LOW
- MEDIUM
- HIGH
- VERY_HIGH

## Explainability

Ogni Opportunity Score deve fornire:

- score;
- confidence;
- top reasons;
- fattori positivi;
- fattori negativi;
- servizio consigliato.

## Regola fondamentale

Non usare un solo score opaco.

Il sistema deve spiegare perché un'azienda è stata classificata come opportunità.

## Growth Potential Score (aziende senza sito)

L'Opportunity Score sopra richiede un audit su un sito esistente. Per le aziende
scoperte senza sito (discovery estesa) non c'è nulla da analizzare, quindi si usa
un punteggio euristico separato, il **Growth Potential Score**, calcolato da:

- categoria (quanto quel tipo di attività dipende dalla scoperta online);
- competition gap (quota di attività simili nella stessa zona che hanno già un sito);
- contattabilità (telefono/email noti);
- reputazione, se nota da OSM (stelle/rating).

Non è un modello allenato (nessun dato di fatturato/clienti è disponibile): è una
stima esplicativa, stessa logica dell'Opportunity Score (score 0–100, priority,
top reasons, fattori positivi/negativi, servizio consigliato). Serve a non far
sparire in fondo alla pipeline i prospect senza sito, che spesso sono i più
interessanti, e ad alimentare la proposta "creazione sito da zero".
