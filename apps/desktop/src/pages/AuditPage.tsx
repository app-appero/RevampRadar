import { useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import {
  fetchAudit,
  type Audit,
  type AIAnalysis,
  type AuditFinding,
  type OpportunityScore,
  type WebsiteScore,
} from "../api/audits";
import { fetchAuditIntelligence } from "../api/intelligence";
import { fetchAuditProposal, generateProposal, type Proposal } from "../api/proposals";
import { IntelligencePanel } from "../components/IntelligencePanel";
import { formatRelativeDay, priorityLabel } from "../components/mobile";
import { PageBackLink } from "../components/HistoryNav";
import { ProgressBar } from "../components/ProgressBar";
import { ProposalCard } from "../components/ProposalCard";
import { ScreenshotGallery } from "../components/ScreenshotGallery";
import { ExternalLink } from "../components/ExternalLink";
import { CompanyAuditHistory } from "../components/CompanyAuditHistory";
import { CompanyContacts } from "../components/CompanyContacts";

export function AuditPage() {
  const { auditId } = useParams();
  const auditQuery = useQuery({
    queryKey: ["audit", auditId],
    queryFn: () => fetchAudit(auditId!),
    enabled: Boolean(auditId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 1000 : false;
    },
  });

  const [showDetails, setShowDetails] = useState(false);
  const audit = auditQuery.data;
  const inProgress = audit?.status === "queued" || audit?.status === "running";
  const proposalQuery = useQuery({
    queryKey: ["proposal", auditId],
    queryFn: () => fetchAuditProposal(auditId!),
    enabled: Boolean(auditId) && audit?.status === "completed",
    retry: false,
  });
  const intelligenceQuery = useQuery({
    queryKey: ["intelligence", auditId],
    queryFn: () => fetchAuditIntelligence(auditId!),
    enabled: Boolean(auditId) && audit?.status === "completed",
    retry: false,
  });
  const generate = useMutation({
    mutationFn: () => generateProposal(auditId!),
    onSuccess: () => {
      void proposalQuery.refetch();
    },
  });

  return (
      <main className="mx-auto flex max-w-5xl flex-col gap-4 px-5 pt-4 pb-28 md:gap-8 md:px-6 md:py-10">
        <PageBackLink fallback="/" label="Indietro" />

        {auditQuery.isError ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            {auditQuery.error instanceof Error
              ? auditQuery.error.message
              : "Impossibile caricare l'audit."}
          </p>
        ) : null}

        {audit ? (
          <>
            <header className="space-y-2">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-[17px] font-bold tracking-tight break-all md:text-3xl md:font-semibold">{audit.domain}</h1>
                <span className={audit.status === "completed" ? "hidden md:inline" : ""}>
                  <StatusPill status={audit.status} />
                </span>
              </div>
              <p className="text-xs text-stone-600 md:hidden">Analizzato {formatRelativeDay(audit.completed_at ?? audit.started_at).toLowerCase()}</p>
              <p className="hidden text-stone-600 md:block">
                <ExternalLink href={audit.normalized_url} className="underline">
                  {audit.normalized_url}
                </ExternalLink>
              </p>
            </header>

            {audit.opportunity_score || audit.website_score ? (
              <ScoresSection
                website={audit.website_score}
                opportunity={audit.opportunity_score}
                ai={audit.ai_analysis}
                showDetails={showDetails}
                extra={
                  <>
                    {audit.opportunity_score && audit.opportunity_score.top_reasons.length > 0 ? (
                      <section className="space-y-2.5 rounded-2xl border border-stone-200 bg-white p-4">
                        <h2 className="text-[15px] font-semibold">Perché vale la pena contattarlo</h2>
                        <ul className="space-y-2 text-sm leading-snug text-stone-800">
                          {audit.opportunity_score.top_reasons.map((reason, index) => (
                            <li key={index} className="flex gap-2.5">
                              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-800" />
                              {reason}
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}
                    <TechChecks audit={audit} />
                  </>
                }
              />
            ) : null}

            {inProgress ? (
              <ProgressBar
                percent={audit.progress_percent ?? 0}
                label={audit.progress_label ?? "Analisi in corso"}
                hint="I finding compariranno al termine della scansione."
              />
            ) : null}

            {audit.status === "failed" ? (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
                Analisi fallita{audit.error_message ? `: ${audit.error_message}` : "."}
              </p>
            ) : null}

            <button
              type="button"
              onClick={() => setShowDetails((value) => !value)}
              aria-expanded={showDetails}
              className="h-12 rounded-xl border border-stone-300 text-sm font-semibold text-stone-700 md:hidden"
            >
              {showDetails ? "Nascondi dettagli completi" : "Mostra dettagli completi"}
            </button>

            <div className={`${showDetails ? "flex flex-col gap-8" : "hidden"} md:contents`}>

            {audit.company_id && audit.status === "completed" ? (
              <>
                <CompanyContacts companyId={audit.company_id} />
                <CompanyAuditHistory companyId={audit.company_id} currentAuditId={audit.id} />
              </>
            ) : null}

            {audit.screenshots.length > 0 ? (
              <ScreenshotGallery shots={audit.screenshots} />
            ) : !inProgress ? (
              <p className="rounded-lg bg-stone-100 px-3 py-2 text-sm text-stone-600">
                Nessuno screenshot. Se tra i finding c’è “Screenshot non disponibile”,
                Chromium non era pronto: rilancia l’analisi dopo che l’API Docker è avviata.
              </p>
            ) : null}

            {intelligenceQuery.data ? <IntelligencePanel data={intelligenceQuery.data} /> : null}

            {audit.status === "completed" ? (
              <ProposalSection
                proposal={proposalQuery.data}
                pending={generate.isPending}
                error={generate.isError}
                aiError={generate.data?.ai_error ?? null}
                onGenerate={() => generate.mutate()}
              />
            ) : null}

            <section className="grid gap-4 sm:grid-cols-3">
              <Metric
                label="HTTPS"
                value={audit.http?.https === true ? "sì" : audit.http ? "no" : "—"}
              />
              <Metric
                label="Status"
                value={audit.http?.status_code != null ? String(audit.http.status_code) : "—"}
              />
              <Metric
                label="Tempo risposta"
                value={
                  audit.http?.response_time_ms != null
                    ? `${String(audit.http.response_time_ms)} ms`
                    : "—"
                }
              />
            </section>

            <PerformanceSection data={audit.performance} />

            <section className="space-y-3">
              <h2 className="text-lg font-medium">Finding</h2>
              {audit.findings.length === 0 && !inProgress ? (
                <p className="text-sm text-stone-500">Nessun finding registrato.</p>
              ) : (
                <ul className="space-y-3">
                  {audit.findings.map((finding) => (
                    <FindingCard key={finding.id} finding={finding} />
                  ))}
                </ul>
              )}
            </section>
            </div>

            {audit.status === "completed" ? (
              <div className="fixed inset-x-0 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-10 flex gap-2.5 border-t border-stone-200 bg-white px-5 py-3 md:hidden">
                {audit.company_id ? (
                  <Link
                    to={`/companies/${audit.company_id}`}
                    className="flex h-12 flex-1 items-center justify-center rounded-xl bg-stone-900 text-[15px] font-semibold text-white"
                  >
                    Scheda azienda
                  </Link>
                ) : null}
                <button
                  type="button"
                  disabled={generate.isPending}
                  onClick={() => generate.mutate()}
                  className="h-12 flex-1 rounded-xl border border-stone-400 text-[15px] font-semibold text-stone-900 disabled:opacity-50"
                >
                  {generate.isPending ? "Genero…" : "Genera proposta"}
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </main>
  );
}

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    queued: "bg-stone-100 text-stone-700",
    running: "bg-amber-100 text-amber-900",
    completed: "bg-emerald-100 text-emerald-800",
    failed: "bg-red-100 text-red-800",
  };
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${styles[status] ?? styles.queued}`}>
      {status}
    </span>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
      <p className="text-xs tracking-wide text-stone-500 uppercase">{label}</p>
      <p className="mt-1 text-lg font-medium">{value}</p>
    </div>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function metricNumber(value: unknown): string {
  return typeof value === "number" ? String(value) : "—";
}

function PerformanceSection({ data }: { data: Record<string, unknown> | null }) {
  const browser = asRecord(data?.browser);
  const pagespeed = asRecord(data?.pagespeed);
  if (!browser && !pagespeed) return null;
  const vitals = asRecord(pagespeed?.core_web_vitals);
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-medium">Performance</h2>
      <div className="grid gap-4 sm:grid-cols-3">
        <Metric
          label="Load (browser)"
          value={browser?.load_time_ms != null ? `${metricNumber(browser.load_time_ms)} ms` : "—"}
        />
        <Metric
          label="DCL (browser)"
          value={
            browser?.dom_content_loaded_ms != null
              ? `${metricNumber(browser.dom_content_loaded_ms)} ms`
              : "—"
          }
        />
        <Metric
          label="Transfer"
          value={browser?.transfer_size != null ? `${metricNumber(browser.transfer_size)} B` : "—"}
        />
      </div>
      {pagespeed ? (
        pagespeed.ok === false ? (
          <p className="text-sm text-stone-500">
            PageSpeed non disponibile{typeof pagespeed.error === "string" ? `: ${pagespeed.error}` : "."}
          </p>
        ) : (
          <>
            <p className="text-xs text-stone-500">PageSpeed Insights (Lighthouse remoto)</p>
            <div className="grid gap-4 sm:grid-cols-4">
              <Metric label="PSI Performance" value={metricNumber(pagespeed.performance)} />
              <Metric label="Accessibilità" value={metricNumber(pagespeed.accessibility)} />
              <Metric label="Best practices" value={metricNumber(pagespeed.best_practices)} />
              <Metric label="SEO PSI" value={metricNumber(pagespeed.seo)} />
            </div>
            {vitals ? (
              <p className="text-sm text-stone-600">
                LCP {typeof vitals["largest-contentful-paint"] === "string" ? vitals["largest-contentful-paint"] : "n/d"}
                {" · "}
                CLS {typeof vitals["cumulative-layout-shift"] === "string" ? vitals["cumulative-layout-shift"] : "n/d"}
                {" · "}
                INP {typeof vitals["interaction-to-next-paint"] === "string" ? vitals["interaction-to-next-paint"] : "n/d"}
              </p>
            ) : null}
          </>
        )
      ) : (
        <p className="text-sm text-stone-500">
          PageSpeed Insights è opzionale: imposta PAGESPEED_API_KEY per Lighthouse remoto. Lighthouse locale resta rimandato.
        </p>
      )}
    </section>
  );
}

function ScoresSection({
  website,
  opportunity,
  ai,
  showDetails,
  extra,
}: {
  website: WebsiteScore | null;
  opportunity: OpportunityScore | null;
  ai: AIAnalysis | null;
  showDetails: boolean;
  extra: ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:hidden">
        {website ? (
          <div className="flex flex-col gap-1 rounded-2xl border border-stone-200 bg-white p-3.5">
            <span className="text-xs font-semibold text-stone-600">Website Score</span>
            <span className="text-4xl leading-none font-bold tracking-tight">
              {website.overall_score}
              <span className="text-base font-medium text-stone-500">/100</span>
            </span>
            <div className="mt-1.5 h-1.5 rounded-full bg-stone-200">
              <div className="h-1.5 rounded-full bg-amber-500" style={{ width: `${Math.min(100, website.overall_score)}%` }} />
            </div>
            <span className="mt-1 text-xs text-stone-600">Qualità del sito</span>
          </div>
        ) : null}
        {opportunity ? (
          <div className="flex flex-col gap-1 rounded-2xl bg-emerald-100 p-3.5 text-[#ffffff]">
            <span className="text-xs font-semibold text-emerald-800">Opportunity Score</span>
            <span className="text-4xl leading-none font-bold tracking-tight">{priorityLabel(opportunity.priority)}</span>
            <div className="mt-1.5 h-1.5 rounded-full bg-[#065f46]">
              <div className="h-1.5 rounded-full bg-emerald-700" style={{ width: `${Math.min(100, opportunity.opportunity_score)}%` }} />
            </div>
            <span className="mt-1 text-xs text-[#d1fae5]">Valore commerciale</span>
          </div>
        ) : null}
      </div>
      <div className="space-y-4 md:hidden">{extra}</div>
      <div className="hidden gap-4 md:grid md:grid-cols-3">
        {website ? (
          <ScoreCard
            label="Website Score"
            hint="Alto = sito già buono"
            value={website.overall_score}
            tone="site"
          />
        ) : null}
        {opportunity ? (
          <ScoreCard
            label="Business Score"
            hint="Preliminare, solo dal sito"
            value={opportunity.business_score}
            tone="neutral"
          />
        ) : null}
        {opportunity ? (
          <ScoreCard
            label="Opportunity Score"
            hint="Alto = vale la pena contattare"
            value={opportunity.opportunity_score}
            tone="opportunity"
            badge={opportunity.priority}
          />
        ) : null}
      </div>

      {opportunity ? (
        <div className={`${showDetails ? "" : "hidden"} rounded-2xl border border-stone-200 bg-white p-5 md:block`}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-medium">Perché è un’opportunità</h2>
            <p className="text-xs text-stone-500">
              Confidence {Math.round(opportunity.confidence * 100)}%
            </p>
          </div>
          <p className="mt-2 text-sm text-stone-600">{opportunity.explanation}</p>
          <p className="mt-3 text-sm font-medium text-stone-900">
            Servizio consigliato: {opportunity.recommended_service}
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <FactorList title="Motivi principali" items={opportunity.top_reasons} />
            <FactorList title="Fattori positivi" items={opportunity.positive_factors} />
            <FactorList title="Fattori negativi" items={opportunity.negative_factors} />
          </div>
        </div>
      ) : null}

      {website ? (
        <div className={`${showDetails ? "grid" : "hidden"} gap-3 sm:grid-cols-4 md:grid`}>
          <Metric label="Tecnica" value={String(website.technical_score)} />
          <Metric label="SEO" value={String(website.seo_score)} />
          <Metric label="Mobile" value={String(website.mobile_score)} />
          <Metric label="Conversione" value={String(website.conversion_score)} />
          <Metric label="UX" value={String(website.ux_score)} />
          <Metric
            label="UI"
            value={website.ui_score != null ? String(website.ui_score) : "n/d"}
          />
          <Metric label="Performance" value={String(website.performance_score)} />
          <Metric label="Trust" value={String(website.trust_score)} />
        </div>
      ) : null}

      {ai ? <AIBlock ai={ai} /> : null}
    </section>
  );
}

function ScoreCard({
  label,
  hint,
  value,
  tone,
  badge,
}: {
  label: string;
  hint: string;
  value: number;
  tone: "site" | "opportunity" | "neutral";
  badge?: string;
}) {
  const colors = {
    site: value >= 70 ? "text-emerald-800" : value >= 45 ? "text-amber-800" : "text-red-800",
    opportunity: value >= 60 ? "text-indigo-800" : value >= 45 ? "text-amber-800" : "text-stone-700",
    neutral: "text-stone-900",
  };
  return (
    <div className="rounded-2xl border border-stone-200 bg-white px-4 py-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs tracking-wide text-stone-500 uppercase">{label}</p>
        {badge ? <PriorityPill priority={badge} /> : null}
      </div>
      <p className={`mt-1 text-3xl font-semibold ${colors[tone]}`}>{value}</p>
      <p className="mt-1 text-xs text-stone-500">{hint}</p>
    </div>
  );
}

function PriorityPill({ priority }: { priority: string }) {
  const styles: Record<string, string> = {
    LOW: "bg-stone-100 text-stone-700",
    MEDIUM: "bg-amber-100 text-amber-900",
    HIGH: "bg-orange-100 text-orange-800",
    VERY_HIGH: "bg-red-100 text-red-800",
  };
  const labels: Record<string, string> = {
    LOW: "Bassa",
    MEDIUM: "Media",
    HIGH: "Alta",
    VERY_HIGH: "Molto alta",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[priority] ?? styles.LOW}`}>
      {labels[priority] ?? priority}
    </span>
  );
}

function FactorList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return (
      <div>
        <h3 className="text-xs tracking-wide text-stone-500 uppercase">{title}</h3>
        <p className="mt-2 text-sm text-stone-500">Nessun elemento.</p>
      </div>
    );
  }
  return (
    <div>
      <h3 className="text-xs tracking-wide text-stone-500 uppercase">{title}</h3>
      <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-stone-700">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function AIBlock({ ai }: { ai: AIAnalysis }) {
  if (ai.status === "skipped") {
    return (
      <p className="text-sm text-stone-500">
        Analisi AI non eseguita
        {ai.reason === "missing_api_key" ? ": manca OPENAI_API_KEY." : "."} I punteggi tecnici restano validi.
      </p>
    );
  }
  if (ai.status === "failed") {
    return (
      <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
        Analisi AI non disponibile{ai.error ? `: ${ai.error}` : "."} L’audit tecnico è comunque valido.
      </p>
    );
  }
  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-medium">Lettura qualitativa (AI)</h2>
      <p className="mt-1 text-xs text-stone-500">
        Prompt {ai.prompt_version ?? "—"}
        {ai.confidence != null ? ` · confidence ${Math.round(ai.confidence * 100)}%` : ""}
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <FactorList title="Punti di forza" items={ai.strengths} />
        <FactorList title="Debolezze" items={ai.weaknesses} />
      </div>
      {ai.recommendations.length > 0 ? (
        <div className="mt-4">
          <FactorList title="Raccomandazioni" items={ai.recommendations} />
        </div>
      ) : null}
    </div>
  );
}

function ProposalSection({
  proposal,
  pending,
  error,
  aiError,
  onGenerate,
}: {
  proposal: Proposal | null | undefined;
  pending: boolean;
  error: boolean;
  aiError: string | null;
  onGenerate: () => void;
}) {
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-medium">Proposta commerciale</h2>
          <p className="text-sm text-stone-500">
            Summary, email da copiare e stima interna. Il prezzo non va in email. L’AI è opzionale: senza chiave resta il testo deterministico.
          </p>
        </div>
        <button
          type="button"
          disabled={pending}
          onClick={onGenerate}
          className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
        >
          {pending ? "Generazione…" : proposal ? "Rigenera proposta" : "Genera proposta"}
        </button>
      </div>
      {error ? (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">Proposta non generata.</p>
      ) : null}
      {aiError ? (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
          AI non riuscita, usata la proposta deterministica: {aiError}
        </p>
      ) : null}
      {proposal ? <ProposalCard proposal={proposal} /> : null}
    </section>
  );
}

function FindingCard({ finding }: { finding: AuditFinding }) {
  const colors: Record<string, string> = {
    critical: "bg-red-100 text-red-800",
    high: "bg-orange-100 text-orange-800",
    medium: "bg-amber-100 text-amber-900",
    low: "bg-stone-100 text-stone-700",
    info: "bg-sky-100 text-sky-800",
  };
  return (
    <li className="rounded-2xl border border-stone-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${colors[finding.severity] ?? colors.info}`}
        >
          {finding.severity}
        </span>
        <span className="text-xs text-stone-400">{finding.code}</span>
      </div>
      <h3 className="mt-2 font-medium">{finding.title}</h3>
      <p className="mt-1 text-sm text-stone-600">{finding.description}</p>
      {finding.evidence ? (
        <p className="mt-2 text-xs break-all text-stone-500">Evidenza: {finding.evidence}</p>
      ) : null}
      <p className="mt-2 text-sm text-stone-800">{finding.recommendation}</p>
    </li>
  );
}

function TechChecks({ audit }: { audit: Audit }) {
  const website = audit.website_score;
  const rows: { label: string; value: string; tone: "ok" | "warn" | "bad" }[] = [];
  if (audit.http) {
    rows.push({ label: "HTTPS", value: audit.http.https ? "OK" : "Assente", tone: audit.http.https ? "ok" : "bad" });
    const ms = audit.http.response_time_ms;
    if (typeof ms === "number") {
      rows.push({ label: "Tempo risposta", value: `${(ms / 1000).toFixed(1).replace(".", ",")} s`, tone: ms > 1500 ? "warn" : "ok" });
    }
  }
  if (website) {
    rows.push({ label: "Mobile", value: `${website.mobile_score}/100`, tone: website.mobile_score < 60 ? "warn" : "ok" });
    rows.push({ label: "SEO", value: `${website.seo_score}/100`, tone: website.seo_score < 40 ? "bad" : website.seo_score < 60 ? "warn" : "ok" });
  }
  if (rows.length === 0) return null;
  const tones = {
    ok: "bg-emerald-100 text-emerald-800",
    warn: "bg-amber-100 text-amber-800",
    bad: "bg-red-100 text-red-800",
  };
  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4">
      <h2 className="mb-1.5 text-[15px] font-semibold">Controlli tecnici</h2>
      {rows.map((row, index) => (
        <div
          key={row.label}
          className={`flex min-h-9 items-center justify-between text-sm ${index < rows.length - 1 ? "border-b border-stone-100" : ""}`}
        >
          <span>{row.label}</span>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${tones[row.tone]}`}>{row.value}</span>
        </div>
      ))}
    </section>
  );
}
