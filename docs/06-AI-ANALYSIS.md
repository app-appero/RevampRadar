# 06 — AI Analysis

## Obiettivo

Valutare aspetti qualitativi non facilmente misurabili con scanner tradizionali.

## Input

- screenshot desktop;
- screenshot mobile;
- finding tecnici;
- metadata;
- contenuto testuale selezionato;
- CTA;
- struttura pagina.

## Dimensioni

- UI;
- UX;
- mobile usability;
- conversion;
- copy;
- trust/credibility;
- visual hierarchy.

## Output

JSON strutturato.

Esempio concettuale:

- scores
- findings
- strengths
- weaknesses
- recommendations
- confidence

## Regole

1. non inventare dati aziendali;
2. distinguere osservazioni da inferenze;
3. ogni finding deve avere evidenza;
4. evitare giudizi puramente estetici senza motivazione;
5. privilegiare impatto su usabilità e conversione;
6. restituire output validabile.

## Severity

- low
- medium
- high
- critical

## Prompt versioning

Ogni prompt di analisi deve avere una versione.

Salvare la versione usata nell'audit.

## Fallback

Se l'AI fallisce, l'audit tecnico deve rimanere valido.

L'AI è un arricchimento, non un requisito per la parte deterministica.
