import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  fetchBulkScan,
  fetchCompanies,
  fetchDiscovery,
  formatOsmTags,
  retryFailedScan,
  startBulkScan,
  type BulkScan,
  type CompanySummary,
} from "../api/discovery";
import { PageBackLink } from "../components/HistoryNav";
import { ProgressBar } from "../components/ProgressBar";

const PAGE_SIZE = 20;

export function DiscoveryRunPage() {
  const { runId } = useParams();
  const query = useQuery({
    queryKey: ["discovery", runId],
    queryFn: () => fetchDiscovery(runId!),
    enabled: Boolean(runId),
    refetchInterval: (current) => {
      const status = current.state.data?.status;
      return status === "queued" || status === "running" ? 1000 : false;
    },
  });
  const run = query.data;
  const inProgress = run?.status === "queued" || run?.status === "running";
  const startScan = useMutation({
    mutationFn: () => startBulkScan(runId!),
    onSuccess: () => {
      void query.refetch();
    },
  });
  const retryScan = useMutation({
    mutationFn: () => {
      const id = run?.latest_scan_id ?? startScan.data?.id;
      if (!id) {
        throw new Error("Nessuna scansione da ritentare.");
      }
      return retryFailedScan(id);
    },
    onSuccess: () => {
      void query.refetch();
    },
  });
  const scanId = run?.latest_scan_id ?? startScan.data?.id ?? retryScan.data?.id;
  const scanQuery = useQuery({
    queryKey: ["bulk-scan", scanId],
    queryFn: () => fetchBulkScan(scanId!),
    enabled: Boolean(scanId),
    refetchInterval: (current) => {
      const status = current.state.data?.status;
      return status === "queued" || status === "running" ? 1000 : false;
    },
  });

  return (
      <main className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
        <PageBackLink fallback="/discovery" label="Indietro" />

        {query.isError ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            {query.error instanceof Error ? query.error.message : "Impossibile caricare la discovery."}
          </p>
        ) : null}

        {run ? (
          <>
            <header className="space-y-2">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-tight">
                  {run.industry} — {run.location}
                </h1>
                <span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-medium text-stone-700">
                  {run.status}
                </span>
                {run.extended ? (
                  <span className="rounded-full bg-sky-100 px-3 py-1 text-xs font-medium text-sky-800">
                    ricerca estesa
                  </span>
                ) : null}
              </div>
              <p className="text-sm text-stone-500">
                Provider {run.provider} · {run.total_found} aziende · max {run.max_results}
                {run.osm_tags?.length ? ` · tag OSM ${formatOsmTags(run.osm_tags)}` : ""}
              </p>
            </header>

            {run.status !== "failed" && run.error_message ? (
              <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                {run.error_message}
              </p>
            ) : null}

            {inProgress ? (
              <ProgressBar
                percent={run.progress_percent ?? 0}
                label={run.progress_label ?? "Ricerca in corso"}
                hint="OpenStreetMap può richiedere fino a un minuto per un’area ampia."
              />
            ) : null}

            {run.status === "failed" ? (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
                Discovery fallita{run.error_message ? `: ${run.error_message}` : "."}
              </p>
            ) : null}

            {run.status === "completed" && run.total_found > 0 ? (
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={startScan.isPending || scanQuery.data?.status === "queued" || scanQuery.data?.status === "running"}
                  onClick={() => startScan.mutate()}
                  className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
                >
                  {startScan.isPending ? "Avvio…" : "Analizza tutti i siti"}
                </button>
                {scanQuery.data?.progress.failed ? (
                  <button
                    type="button"
                    disabled={retryScan.isPending || !scanId}
                    onClick={() => retryScan.mutate()}
                    className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50 disabled:opacity-50"
                  >
                    Riprova i falliti
                  </button>
                ) : null}
              </div>
            ) : null}

            {startScan.isError ? (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
                {startScan.error instanceof Error ? startScan.error.message : "Scansione non avviata."}
              </p>
            ) : null}

            {scanQuery.data ? <BulkScanPanel scan={scanQuery.data} /> : null}

            <CompanyTable companies={run.companies} empty={!inProgress} />
          </>
        ) : null}
      </main>
  );
}

function BulkScanPanel({ scan }: { scan: BulkScan }) {
  const p = scan.progress;
  const scanning = scan.status === "queued" || scan.status === "running";
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-medium">Ranking opportunità</h2>
        <p className="text-xs text-stone-500">
          {scan.status} · {p.completed}/{p.total} completati
          {p.failed ? ` · ${p.failed} falliti` : ""}
          {p.skipped ? ` · ${p.skipped} senza sito` : ""}
        </p>
      </div>
      {scanning ? (
        <ProgressBar
          percent={p.percent ?? 0}
          label={p.label || `Analisi siti · ${p.completed}/${p.total}`}
          hint="I siti senza URL vengono saltati; i falliti si possono ritentare."
        />
      ) : null}
      {scan.status === "failed" && scan.error_message ? (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{scan.error_message}</p>
      ) : null}
      <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-stone-50 text-xs tracking-wide text-stone-500 uppercase">
            <tr>
              <th className="px-4 py-3">Azienda</th>
              <th className="px-4 py-3">Stato</th>
              <th className="px-4 py-3">Website</th>
              <th className="px-4 py-3">Opportunity</th>
              <th className="px-4 py-3">Priorità</th>
            </tr>
          </thead>
          <tbody>
            {scan.items.map((item) => (
              <tr key={item.id} className="border-t border-stone-100">
                <td className="px-4 py-3">
                  <Link to={`/companies/${item.company_id}`} className="font-medium hover:underline">
                    {item.company_name}
                  </Link>
                  <p className="text-xs text-stone-500">{item.domain ?? item.city ?? "—"}</p>
                </td>
                <td className="px-4 py-3 text-stone-600">{item.status}</td>
                <td className="px-4 py-3">{item.website_score ?? "—"}</td>
                <td className="px-4 py-3 font-medium">{item.opportunity_score ?? "—"}</td>
                <td className="px-4 py-3">
                  {item.audit_id ? (
                    <Link to={`/audits/${item.audit_id}`} className="text-stone-800 underline">
                      {item.priority ?? "audit"}
                    </Link>
                  ) : (
                    <span className="text-stone-500">{item.priority ?? "—"}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function CompaniesPage() {
  const query = useQuery({
    queryKey: ["companies"],
    queryFn: fetchCompanies,
  });

  return (
      <main className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
        <PageBackLink fallback="/discovery" label="Indietro" />
        <header>
          <h1 className="text-3xl font-semibold tracking-tight">Aziende</h1>
          <p className="mt-1 text-sm text-stone-500">Tutte le aziende persistite dalle ricerche.</p>
        </header>
        {query.isError ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            {query.error instanceof Error ? query.error.message : "Impossibile caricare le aziende."}
          </p>
        ) : null}
        <CompanyTable companies={query.data ?? []} empty={query.isSuccess} />
      </main>
  );
}

function CompanyTable({ companies, empty }: { companies: CompanySummary[]; empty: boolean }) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(companies.length / PAGE_SIZE));
  const current = Math.min(page, totalPages);
  const slice = useMemo(() => {
    const start = (current - 1) * PAGE_SIZE;
    return companies.slice(start, start + PAGE_SIZE);
  }, [companies, current]);
  const withoutSite = companies.filter((item) => !item.website_url && !item.domain).length;

  if (companies.length === 0 && empty) {
    return <p className="text-sm text-stone-500">Nessuna azienda trovata per questo settore.</p>;
  }
  return (
    <div className="space-y-3">
      {companies.length > 0 ? (
        <p className="text-xs text-stone-500">
          {companies.length} aziend{companies.length === 1 ? "a" : "e"}
          {withoutSite ? ` · ${withoutSite} senza sito` : ""}
          {companies.length > PAGE_SIZE ? ` · pagina ${current}/${totalPages}` : ""}
        </p>
      ) : null}
      <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-stone-50 text-xs tracking-wide text-stone-500 uppercase">
            <tr>
              <th className="px-4 py-3">Azienda</th>
              <th className="px-4 py-3">Città</th>
              <th className="px-4 py-3">Sito</th>
            </tr>
          </thead>
          <tbody>
            {slice.map((company) => (
              <tr key={company.id} className="border-t border-stone-100">
                <td className="px-4 py-3">
                  <Link to={`/companies/${company.id}`} className="font-medium hover:underline">
                    {company.name}
                  </Link>
                  {company.category ? (
                    <p className="text-xs text-stone-500">{company.category}</p>
                  ) : null}
                  {company.osm_tags ? (
                    <p className="text-xs text-stone-400">{formatOsmTags(company.osm_tags)}</p>
                  ) : null}
                  {company.osm_start_date ? (
                    <p className="text-xs text-stone-400">Apertura {company.osm_start_date}</p>
                  ) : null}
                </td>
                <td className="px-4 py-3 text-stone-600">{company.city ?? "—"}</td>
                <td className="px-4 py-3 text-stone-600">
                  {company.domain ?? company.website_url ?? (
                    <span className="text-sky-800">Senza sito</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 ? (
        <div className="flex items-center justify-between text-sm">
          <button
            type="button"
            disabled={current <= 1}
            onClick={() => setPage(current - 1)}
            className="rounded-lg border border-stone-300 px-3 py-1.5 disabled:opacity-40"
          >
            Precedente
          </button>
          <span className="text-stone-500">
            {current} / {totalPages}
          </span>
          <button
            type="button"
            disabled={current >= totalPages}
            onClick={() => setPage(current + 1)}
            className="rounded-lg border border-stone-300 px-3 py-1.5 disabled:opacity-40"
          >
            Successiva
          </button>
        </div>
      ) : null}
    </div>
  );
}
