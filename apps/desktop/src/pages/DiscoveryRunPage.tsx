import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import {
  fetchBulkScan,
  fetchCompanies,
  fetchDiscovery,
  retryFailedScan,
  startBulkScan,
  type BulkScan,
  type CompanySummary,
} from "../api/discovery";
import { AppShell } from "../components/AppShell";

export function DiscoveryRunPage() {
  const { runId } = useParams();
  const query = useQuery({
    queryKey: ["discovery", runId],
    queryFn: () => fetchDiscovery(runId!),
    enabled: Boolean(runId),
    refetchInterval: (current) => {
      const status = current.state.data?.status;
      return status === "queued" || status === "running" ? 2000 : false;
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
      return status === "queued" || status === "running" ? 2000 : false;
    },
  });

  return (
    <AppShell>
      <main className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
        <Link to="/discovery" className="text-sm text-stone-500 hover:text-stone-900">
          ← Nuova ricerca
        </Link>

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
              </div>
              <p className="text-sm text-stone-500">
                Provider {run.provider} · {run.total_found} aziende · max {run.max_results}
              </p>
            </header>

            {inProgress ? (
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                Ricerca in corso su OpenStreetMap. Può richiedere fino a un minuto per un’area ampia.
              </p>
            ) : null}

            {run.status === "failed" ? (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
                Discovery fallita{run.error_message ? `: ${run.error_message}` : "."}
              </p>
            ) : null}

            {run.status === "completed" ? (
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
    </AppShell>
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
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Analisi in batch in corso. I siti senza URL vengono saltati; i falliti si possono ritentare.
        </p>
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
    <AppShell>
      <main className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
        <Link to="/discovery" className="text-sm text-stone-500 hover:text-stone-900">
          ← Discovery
        </Link>
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
    </AppShell>
  );
}

function CompanyTable({ companies, empty }: { companies: CompanySummary[]; empty: boolean }) {
  if (companies.length === 0 && empty) {
    return <p className="text-sm text-stone-500">Nessuna azienda trovata.</p>;
  }
  return (
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
          {companies.map((company) => (
            <tr key={company.id} className="border-t border-stone-100">
              <td className="px-4 py-3">
                <Link to={`/companies/${company.id}`} className="font-medium hover:underline">
                  {company.name}
                </Link>
                {company.category ? (
                  <p className="text-xs text-stone-500">{company.category}</p>
                ) : null}
              </td>
              <td className="px-4 py-3 text-stone-600">{company.city ?? "—"}</td>
              <td className="px-4 py-3 text-stone-600">{company.domain ?? company.website_url ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
