import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  fetchBulkScan,
  fetchCompanies,
  fetchDiscovery,
  formatOsmTags,
  retryDiscovery,
  retryFailedScan,
  startBulkScan,
  type BulkScan,
  type CompanySummary,
} from "../api/discovery";
import { PageBackLink } from "../components/HistoryNav";
import { PriorityChip } from "../components/mobile";
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
  const retryRun = useMutation({
    mutationFn: () => retryDiscovery(runId!),
    onSuccess: () => {
      void query.refetch();
    },
  });
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
      <main className="mx-auto flex max-w-5xl flex-col gap-4 px-5 pt-4 pb-28 md:gap-8 md:px-6 md:py-10">
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
                <h1 className="text-[28px] leading-tight font-semibold tracking-tight md:text-3xl">
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

            {run.status === "failed" || run.status === "partial" ? (
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={retryRun.isPending}
                  onClick={() => retryRun.mutate()}
                  className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50 disabled:opacity-50"
                >
                  {retryRun.isPending ? "Riavvio…" : "Riprova ricerca"}
                </button>
                <span className="text-xs text-stone-500">
                  Stessi parametri; le aziende già trovate restano.
                </span>
                {retryRun.isError ? (
                  <span className="text-sm text-red-700">
                    {retryRun.error instanceof Error ? retryRun.error.message : "Riavvio non riuscito."}
                  </span>
                ) : null}
              </div>
            ) : null}

            {(run.status === "completed" || run.status === "partial") && run.total_found > 0 ? (
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
      <ul className="flex flex-col gap-2.5 md:hidden">
        {scan.items.map((item) => (
          <li key={item.id}>
            <Link
              to={`/companies/${item.company_id}`}
              className="flex items-center gap-3 rounded-[14px] border border-stone-200 bg-white px-3.5 py-3"
            >
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <strong className="truncate text-[15px]">{item.company_name}</strong>
                <span className="truncate text-xs text-stone-600">
                  {item.domain ?? item.city ?? "—"}
                  {item.website_score != null ? ` · Sito ${item.website_score}` : ""}
                </span>
              </span>
              <PriorityChip priority={item.priority} />
            </Link>
          </li>
        ))}
      </ul>
      <div className="hidden overflow-x-auto rounded-2xl border border-stone-200 bg-white md:block">
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
                <td className="rr-primary px-4 py-3">
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
      <main className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-6 md:px-6 md:py-10">
        <PageBackLink fallback="/discovery" label="Indietro" />
        <header>
          <h1 className="text-[28px] leading-tight font-semibold tracking-tight md:text-3xl">Aziende</h1>
          <p className="mt-1 hidden text-sm text-stone-500 md:block">Tutte le aziende persistite dalle ricerche.</p>
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
  const [categoryFilter, setCategoryFilter] = useState("");
  const [segmentFilter, setSegmentFilter] = useState<"all" | "refactor" | "greenfield">("all");
  const categories = useMemo(
    () =>
      Array.from(new Set(companies.map((item) => item.category).filter((item): item is string => Boolean(item)))).sort(
        (a, b) => a.localeCompare(b, "it"),
      ),
    [companies],
  );
  const filtered = useMemo(() => {
    const byCategory = categoryFilter ? companies.filter((item) => item.category === categoryFilter) : companies;
    if (segmentFilter === "all") return byCategory;
    return byCategory.filter((item) => Boolean(item.website_url || item.domain) === (segmentFilter === "refactor"));
  }, [companies, categoryFilter, segmentFilter]);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, totalPages);
  const slice = useMemo(() => {
    const start = (current - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, current]);
  const withoutSite = filtered.filter((item) => !item.website_url && !item.domain).length;

  if (companies.length === 0 && empty) {
    return <p className="text-sm text-stone-500">Nessuna azienda trovata per questo settore.</p>;
  }
  return (
    <div className="space-y-3">
      {categories.length > 1 ? (
        <label className="flex items-center gap-2 text-sm text-stone-700">
          <span className="text-xs font-medium tracking-wide text-stone-500 uppercase">Settore</span>
          <select
            value={categoryFilter}
            onChange={(event) => {
              setCategoryFilter(event.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          >
            <option value="">Tutti i settori ({companies.length})</option>
            {categories.map((item) => (
              <option key={item} value={item}>
                {item} ({companies.filter((company) => company.category === item).length})
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {filtered.length > 0 ? (
        <p className="text-xs text-stone-500">
          {filtered.length} aziend{filtered.length === 1 ? "a" : "e"}
          {withoutSite ? ` · ${withoutSite} senza sito` : ""}
          {filtered.length > PAGE_SIZE ? ` · pagina ${current}/${totalPages}` : ""}
        </p>
      ) : (
        <p className="text-xs text-stone-500">Nessuna azienda per questo settore.</p>
      )}
      <div className="flex gap-2 md:hidden">
        {(
          [
            ["all", "Tutte"],
            ["refactor", "Da rifare"],
            ["greenfield", "Da creare"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => {
              setSegmentFilter(value);
              setPage(1);
            }}
            className={`shrink-0 rounded-full px-3.5 py-2 text-[13px] font-medium ${
              segmentFilter === value ? "bg-stone-900 text-white" : "bg-stone-100 text-stone-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <ul className="flex flex-col gap-2.5 md:hidden">
        {slice.map((company) => {
          const hasSite = Boolean(company.website_url || company.domain);
          return (
            <li key={company.id}>
              <Link
                to={`/companies/${company.id}`}
                className="flex items-center gap-3 rounded-[14px] border border-stone-200 bg-white px-3.5 py-3"
              >
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <strong className="truncate text-[15px]">{company.name}</strong>
                  <span className="truncate text-xs text-stone-600">
                    {hasSite ? (company.domain ?? company.website_url) : "Nessun sito"}
                    {company.city ? ` · ${company.city}` : ""}
                  </span>
                </span>
                <span className="shrink-0 rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-semibold text-stone-700">
                  {hasSite ? "Da rifare" : "Da creare"}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="hidden overflow-x-auto rounded-2xl border border-stone-200 bg-white md:block">
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
                <td className="rr-primary px-4 py-3">
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
