import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import {
  fetchAudit,
  screenshotSrc,
  type AIAnalysis,
  type AuditFinding,
  type OpportunityScore,
  type WebsiteScore,
} from "../api/audits";
import { fetchAuditProposal, generateProposal, type Proposal } from "../api/proposals";
import { AppShell } from "../components/AppShell";
import { ProposalCard } from "../components/ProposalCard";

export function AuditPage() {
  const { auditId } = useParams();
  const auditQuery = useQuery({
    queryKey: ["audit", auditId],
    queryFn: () => fetchAudit(auditId!),
    enabled: Boolean(auditId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2000 : false;
    },
  });

  const audit = auditQuery.data;
  const inProgress = audit?.status === "queued" || audit?.status === "running";
  const proposalQuery = useQuery({
    queryKey: ["proposal", auditId],
    queryFn: () => fetchAuditProposal(auditId!),
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
    <AppShell>
      <main className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
        <Link to="/" className="text-sm text-stone-500 hover:text-stone-900">
          ← Nuova analisi
        </Link>

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
                <h1 className="text-3xl font-semibold tracking-tight">{audit.domain}</h1>
                <StatusPill status={audit.status} />
              </div>
              <p className="text-stone-600">{audit.normalized_url}</p>
            </header>

            {inProgress ? (
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                Analisi in corso. I finding compariranno al termine della scansione.
              </p>
            ) : null}

            {audit.status === "failed" ? (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
                Analisi fallita{audit.error_message ? `: ${audit.error_message}` : "."}
              </p>
            ) : null}

            {audit.screenshots.length > 0 ? (
              <section className="grid gap-4 md:grid-cols-2">
                {audit.screenshots.map((shot) => (
                  <figure
                    key={shot.id}
                    className="overflow-hidden rounded-2xl border border-stone-200 bg-white"
                  >
                    <img
                      src={screenshotSrc(shot.url)}
                      alt={`Screenshot ${shot.device}`}
                      className="h-64 w-full object-cover object-top"
                    />
                    <figcaption className="px-4 py-2 text-sm text-stone-500">
                      {shot.device} · {shot.viewport_width}×{shot.viewport_height}
                    </figcaption>
                  </figure>
                ))}
              </section>
            ) : !inProgress ? (
              <p className="rounded-lg bg-stone-100 px-3 py-2 text-sm text-stone-600">
                Nessuno screenshot. Se tra i finding c’è “Screenshot non disponibile”,
                Chromium non era pronto: rilancia l’analisi dopo che l’API Docker è avviata.
              </p>
            ) : null}

            {audit.opportunity_score || audit.website_score ? (
              <ScoresSection
                website={audit.website_score}
                opportunity={audit.opportunity_score}
                ai={audit.ai_analysis}
              />
            ) : null}

            {audit.status === "completed" ? (
              <ProposalSection
                proposal={proposalQuery.data}
                pending={generate.isPending}
                error={generate.isError}
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
          </>
        ) : null}
      </main>
    </AppShell>
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

function ScoresSection({
  website,
  opportunity,
  ai,
}: {
  website: WebsiteScore | null;
  opportunity: OpportunityScore | null;
  ai: AIAnalysis | null;
}) {
  return (
    <section className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
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
        <div className="rounded-2xl border border-stone-200 bg-white p-5">
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
        <div className="grid gap-3 sm:grid-cols-4">
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
  onGenerate,
}: {
  proposal: Proposal | null | undefined;
  pending: boolean;
  error: boolean;
  onGenerate: () => void;
}) {
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-medium">Proposta commerciale</h2>
          <p className="text-sm text-stone-500">
            Summary, problemi prioritari, email e range indicativo. L’AI è opzionale: senza chiave resta il testo deterministico.
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
