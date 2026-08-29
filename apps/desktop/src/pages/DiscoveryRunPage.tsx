import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { fetchCompanies, fetchDiscovery, type CompanySummary } from "../api/discovery";
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

            <CompanyTable companies={run.companies} empty={!inProgress} />
          </>
        ) : null}
      </main>
    </AppShell>
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
