from dataclasses import dataclass

from app.scanner.html import HtmlScanResult
from app.scanner.http import HttpScanResult
from app.scanner.seo import SeoScanResult


@dataclass(frozen=True)
class FindingDraft:
    category: str
    severity: str
    code: str
    title: str
    description: str
    evidence: str | None
    recommendation: str
    source_type: str = "scanner"


def build_findings(
    http_result: HttpScanResult,
    html_result: HtmlScanResult | None,
    seo_result: SeoScanResult | None,
) -> list[FindingDraft]:
    findings: list[FindingDraft] = []

    if not http_result.ok:
        findings.append(
            FindingDraft(
                category="http",
                severity="critical",
                code="HTTP_UNREACHABLE",
                title="Sito non raggiungibile",
                description="La richiesta HTTP non è andata a buon fine.",
                evidence=http_result.error,
                recommendation="Verifica DNS, certificato SSL e che il server risponda.",
            )
        )
        return findings

    if http_result.status_code and http_result.status_code >= 400:
        findings.append(
            FindingDraft(
                category="http",
                severity="critical" if http_result.status_code >= 500 else "high",
                code="HTTP_ERROR_STATUS",
                title=f"Lo status HTTP è {http_result.status_code}",
                description="La pagina principale non restituisce uno status di successo.",
                evidence=str(http_result.status_code),
                recommendation="Correggi la pagina o i redirect in modo che la home risponda 200.",
            )
        )

    if not http_result.https:
        findings.append(
            FindingDraft(
                category="http",
                severity="high",
                code="HTTP_NO_HTTPS",
                title="HTTPS assente",
                description="La pagina finale non è servita su HTTPS.",
                evidence=http_result.final_url,
                recommendation="Attiva un certificato TLS e reindirizza tutto il traffico su HTTPS.",
            )
        )

    if http_result.response_time_ms is not None and http_result.response_time_ms > 2000:
        findings.append(
            FindingDraft(
                category="performance",
                severity="medium" if http_result.response_time_ms < 4000 else "high",
                code="HTTP_SLOW_RESPONSE",
                title="Tempo di risposta elevato",
                description="Il TTFB/tempo di risposta della home è sopra i 2 secondi.",
                evidence=f"{http_result.response_time_ms} ms",
                recommendation="Ottimizza server, cache e payload della pagina iniziale.",
            )
        )

    if html_result is None:
        findings.append(
            FindingDraft(
                category="html",
                severity="high",
                code="HTML_NOT_HTML",
                title="La risposta non è HTML",
                description="Non è stato possibile analizzare la pagina come documento HTML.",
                evidence=http_result.content_type,
                recommendation="Assicurati che la home restituisca un documento HTML.",
            )
        )
        return findings

    if not html_result.title:
        findings.append(
            FindingDraft(
                category="html",
                severity="high",
                code="HTML_MISSING_TITLE",
                title="Title assente",
                description="La pagina non ha un elemento title.",
                evidence=None,
                recommendation="Aggiungi un title unico e descrittivo.",
            )
        )
    elif len(html_result.title) > 65:
        findings.append(
            FindingDraft(
                category="seo",
                severity="low",
                code="SEO_TITLE_TOO_LONG",
                title="Title troppo lungo",
                description="Il title supera i 65 caratteri e può essere tagliato nei risultati di ricerca.",
                evidence=html_result.title,
                recommendation="Riduci il title a una frase chiara entro i 50-60 caratteri.",
            )
        )

    if not html_result.meta_description:
        findings.append(
            FindingDraft(
                category="seo",
                severity="medium",
                code="SEO_MISSING_DESCRIPTION",
                title="Meta description assente",
                description="Manca la meta description.",
                evidence=None,
                recommendation="Aggiungi una meta description di 120-160 caratteri.",
            )
        )

    if not html_result.h1:
        findings.append(
            FindingDraft(
                category="html",
                severity="high",
                code="HTML_MISSING_H1",
                title="H1 assente",
                description="La pagina non ha un heading H1.",
                evidence=None,
                recommendation="Inserisci un solo H1 che descriva l'offerta principale.",
            )
        )
    elif len(html_result.h1) > 1:
        findings.append(
            FindingDraft(
                category="html",
                severity="low",
                code="HTML_MULTIPLE_H1",
                title="Più di un H1",
                description="Sono presenti più heading H1.",
                evidence=", ".join(html_result.h1),
                recommendation="Mantieni un H1 principale e usa H2/H3 per il resto.",
            )
        )

    if not html_result.viewport:
        findings.append(
            FindingDraft(
                category="mobile",
                severity="high",
                code="HTML_MISSING_VIEWPORT",
                title="Viewport mobile assente",
                description="Manca il meta viewport, spesso segnale di un sito non responsive.",
                evidence=None,
                recommendation='Aggiungi <meta name="viewport" content="width=device-width, initial-scale=1">.',
            )
        )

    if not html_result.lang:
        findings.append(
            FindingDraft(
                category="html",
                severity="low",
                code="HTML_MISSING_LANG",
                title="Attributo lang assente",
                description="L'elemento html non dichiara la lingua.",
                evidence=None,
                recommendation='Imposta lang="it" (o la lingua corretta) sul tag html.',
            )
        )

    if not html_result.canonical:
        findings.append(
            FindingDraft(
                category="seo",
                severity="low",
                code="SEO_MISSING_CANONICAL",
                title="Canonical assente",
                description="Non è stato trovato un link rel=canonical.",
                evidence=None,
                recommendation="Aggiungi un canonical verso l'URL preferito della pagina.",
            )
        )

    if html_result.structured_data_count == 0:
        findings.append(
            FindingDraft(
                category="seo",
                severity="info",
                code="SEO_NO_STRUCTURED_DATA",
                title="Dati strutturati assenti",
                description="Non risultano script JSON-LD.",
                evidence=None,
                recommendation="Aggiungi markup LocalBusiness/Organization se applicabile.",
            )
        )

    if not html_result.analytics:
        findings.append(
            FindingDraft(
                category="tracking",
                severity="medium",
                code="TECH_NO_ANALYTICS",
                title="Nessun analytics rilevato",
                description="Non sono stati trovati GTM, GA o pixel evidenti.",
                evidence=None,
                recommendation="Installa almeno un sistema di misurazione delle conversioni.",
            )
        )

    if not html_result.cta_texts:
        findings.append(
            FindingDraft(
                category="conversion",
                severity="medium",
                code="HTML_WEAK_CTA",
                title="CTA poco evidenti",
                description="Non sono stati trovati link o pulsanti con testo di chiamata all'azione.",
                evidence=None,
                recommendation="Rendi visibile un'azione primaria (contatto, prenotazione, acquisto).",
            )
        )

    if seo_result:
        if not seo_result.robots_found:
            findings.append(
                FindingDraft(
                    category="seo",
                    severity="low",
                    code="SEO_NO_ROBOTS",
                    title="robots.txt assente",
                    description="robots.txt non è raggiungibile.",
                    evidence=seo_result.robots_url,
                    recommendation="Pubblica un robots.txt e indica la sitemap.",
                )
            )
        if not seo_result.sitemap_found:
            findings.append(
                FindingDraft(
                    category="seo",
                    severity="low",
                    code="SEO_NO_SITEMAP",
                    title="Sitemap assente",
                    description="sitemap.xml non è stata trovata.",
                    evidence=seo_result.sitemap_url,
                    recommendation="Genera e pubblica una sitemap.xml.",
                )
            )
        if seo_result.noindex:
            findings.append(
                FindingDraft(
                    category="seo",
                    severity="high",
                    code="SEO_NOINDEX",
                    title="Pagina marcata noindex",
                    description="I meta robots indicano noindex.",
                    evidence=None,
                    recommendation="Rimuovi noindex se la pagina deve comparire sui motori di ricerca.",
                )
            )

    return findings
