# 00 — Project

## Nome

RevampRadar

## Vision

RevampRadar è un'applicazione desktop progettata per individuare automaticamente aziende con una presenza digitale migliorabile e trasformarle in opportunità commerciali qualificate.

L'obiettivo non è semplicemente trovare siti web tecnicamente scarsi, ma identificare aziende per le quali un intervento di redesign, sviluppo o ottimizzazione possa rappresentare un reale valore commerciale.

## Utente iniziale

La prima versione è destinata a un singolo utilizzatore.

Non sono previsti inizialmente:

- registrazione;
- autenticazione;
- organizzazioni;
- team;
- ruoli;
- abbonamenti;
- multi-tenancy.

L'architettura non deve impedire una futura evoluzione web/SaaS.

## Core Workflow

Single Website Analysis → Website Score → Opportunity Score → Discovery → Bulk Analysis → Qualification → CRM → Proposal

## Input principali

Esempio Single Website Analyzer:

- URL sito

Esempio Discovery:

- settore;
- località;
- numero massimo risultati;
- eventuali filtri commerciali.

## Output

Per ogni azienda/sito:

- anagrafica;
- sito;
- settore;
- località;
- dati disponibili;
- audit tecnico;
- screenshot desktop/mobile;
- finding;
- Website Score;
- Opportunity Score;
- motivazioni;
- servizio consigliato;
- stato CRM.

## Principio fondamentale

Un sito scarso non rappresenta automaticamente una buona opportunità commerciale.

RevampRadar deve distinguere chiaramente tra:

### Website Quality
Quanto è buono il sito.

### Commercial Opportunity
Quanto vale la pena contattare l'azienda.

## Criterio di successo MVP

L'MVP è valido quando l'utente può inserire manualmente un URL e ottenere:

1. audit tecnico riproducibile;
2. screenshot desktop e mobile;
3. analisi AI strutturata;
4. Website Score;
5. Opportunity Score preliminare;
6. finding prioritizzati;
7. suggerimento commerciale.

Successivamente il sistema deve poter trovare automaticamente aziende reali e applicare lo stesso motore in massa.

## Non-goal iniziali

- scansione mobile app;
- analisi completa di piattaforme private;
- invio massivo automatico di email;
- SaaS pubblico;
- pagamenti;
- gestione team;
- app mobile;
- generazione completa automatica di nuovi siti.
