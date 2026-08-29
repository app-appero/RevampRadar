import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { fetchAudit, screenshotSrc, type AuditFinding } from "../api/audits";
import { AppShell } from "../components/AppShell";

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
