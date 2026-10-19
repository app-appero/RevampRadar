import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  CRM_STATUSES,
  CRM_STATUS_LABELS,
  fetchDashboard,
  fetchOpportunities,
  fetchOpportunityCategories,
  type OpportunityFilters,
} from "../api/crm";
import { BulkEnrichPanel } from "../components/BulkEnrichPanel";
import { ConfirmDelete } from "../components/ConfirmDelete";
import { ApiError } from "../api/health";
import { deleteAllCompanies, deleteCompany } from "../api/purge";

const PRIORITIES = ["VERY_HIGH", "HIGH", "MEDIUM", "LOW"] as const;

const SEGMENTS = [
  { value: "", label: "Tutte" },
  { value: "refactor", label: "Da rifare (con sito)" },
  { value: "greenfield", label: "Da creare (senza sito)" },
] as const;

// Mantiene i filtri durante la navigazione e il reload nella stessa sessione.
function usePipelineFilter<T extends string | boolean>(name: string, initial: T) {
  const key = `revampradar:pipeline:${name}`;
  const [value, setValue] = useState<T>(() => {
    try {
      const saved: unknown = JSON.parse(sessionStorage.getItem(key) ?? "null");
      return typeof saved === typeof initial ? saved as T : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch {
      // La ricerca resta utilizzabile anche se lo storage non e disponibile.
    }
  }, [key, value]);
  return [value, setValue] as const;
}

export function PipelinePage() {
  const [status, setStatus] = usePipelineFilter<string>("status", "");
  const [q, setQ] = usePipelineFilter<string>("q", "");
  const [city, setCity] = usePipelineFilter<string>("city", "");
  const [category, setCategory] = usePipelineFilter<string>("category", "");
  const [tag, setTag] = usePipelineFilter<string>("tag", "");
  const [priority, setPriority] = usePipelineFilter<string>("priority", "");
  const [minScore, setMinScore] = usePipelineFilter<string>("minScore", "");
  const [shortlist, setShortlist] = usePipelineFilter<boolean>("shortlist", false);
  const [favorite, setFavorite] = usePipelineFilter<boolean>("favorite", false);
  const [segment, setSegment] = usePipelineFilter<"" | "refactor" | "greenfield">("segment", "");
  const [contactableOnly, setContactableOnly] = usePipelineFilter<boolean>("contactableOnly", false);

  const filters = useMemo<OpportunityFilters>(
    () => ({
      status: status || undefined,
      q: q.trim() || undefined,
      city: city.trim() || undefined,
      category: category.trim() || undefined,
      tag: tag.trim() || undefined,
      priority: priority || undefined,
      min_score: minScore ? Number(minScore) : undefined,
      shortlist: shortlist || undefined,
      favorite: favorite || undefined,
      segment: segment || undefined,
      contactable: contactableOnly || undefined,
    }),
    [status, q, city, category, tag, priority, minScore, shortlist, favorite, segment, contactableOnly],
  );

  const dashboardQuery = useQuery({
    queryKey: ["crm-dashboard"],
    queryFn: fetchDashboard,
  });
  const listQuery = useQuery({
    queryKey: ["opportunities", filters],
    queryFn: () => fetchOpportunities(filters),
  });
  const categoryFilters = { ...filters, category: undefined };
  const categoriesQuery = useQuery({
    queryKey: ["opportunities", "categories", categoryFilters],
    queryFn: () => fetchOpportunityCategories(categoryFilters),
  });
  useEffect(() => {
    if (!category || !categoriesQuery.isSuccess || categoriesQuery.isFetching) return;
    const match = categoriesQuery.data.find((item) => item.value === category || item.variants.includes(category));
    if (!match) setCategory("");
    else if (match.value !== category) setCategory(match.value);
  }, [category, categoriesQuery.data, categoriesQuery.isSuccess, categoriesQuery.isFetching, setCategory]);
  // La selezione appartiene alla ricerca corrente, mai a risultati nascosti.
  const filterKey = JSON.stringify(filters);
  const [selection, setSelection] = useState<{ key: string; ids: string[] }>({ key: "", ids: [] });
  if (selection.key !== filterKey) {
    setSelection({ key: filterKey, ids: [] });
  }
  const rows = listQuery.data ?? [];
  const selectedIds = selection.key === filterKey ? selection.ids : [];
  const selectedRows = rows.filter((item) => selectedIds.includes(item.company_id));
  const allSelected = rows.length > 0 && selectedRows.length === rows.length;
  const toggleRow = (id: string, checked: boolean) => setSelection({
    key: filterKey,
    ids: checked ? [...selectedIds, id] : selectedIds.filter((value) => value !== id),
  });
  const dash = dashboardQuery.data;
  const [purgeError, setPurgeError] = useState<string | null>(null);
  const purge = useMutation({
    mutationFn: (action: () => Promise<number>) => action(),
    onMutate: () => setPurgeError(null),
    onError: (err) => {
      setPurgeError(err instanceof ApiError ? err.message : "Eliminazione non riuscita.");
    },
  });

  return (
      <main className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-10">
        <header className="space-y-2">
          <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">CRM</p>
          <h1 className="text-3xl font-semibold tracking-tight">Pipeline</h1>
          <p className="max-w-2xl text-stone-600">
            Qualifica le aziende scoperte: stato commerciale, shortlist, score e filtri.
          </p>
        </header>

        {dashboardQuery.isError || listQuery.isError ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            Impossibile caricare la pipeline. Verifica che l’API sia avviata.
          </p>
        ) : null}

        {dash ? (
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="Totale"
              value={dash.total}
              onClick={() => {
                setStatus("");
                setShortlist(false);
                setFavorite(false);
                setPriority("");
                setMinScore("");
              }}
            />
            <Stat
              label="Alta priorità"
              value={dash.high_priority}
              onClick={() => {
                setPriority("");
                setMinScore("60");
                setShortlist(false);
                setFavorite(false);
                setStatus("");
              }}
            />
            <Stat
              label="Shortlist"
              value={dash.shortlisted}
              onClick={() => {
                setShortlist(true);
                setFavorite(false);
                setStatus("");
                setPriority("");
              }}
            />
            <Stat
              label="Da contattare"
              value={dash.to_contact}
              onClick={() => {
                setStatus("to_contact");
                setShortlist(false);
                setFavorite(false);
              }}
            />
          </section>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {SEGMENTS.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => setSegment(item.value)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                segment === item.value ? "bg-stone-900 text-white" : "bg-stone-100 text-stone-700 hover:bg-stone-200"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {dash ? (
          <div className="flex flex-wrap gap-2">
            {CRM_STATUSES.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => {
                  setStatus(status === item ? "" : item);
                  setShortlist(false);
                  setFavorite(false);
                }}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  status === item ? "bg-stone-900 text-white" : "bg-stone-100 text-stone-700 hover:bg-stone-200"
                }`}
              >
                {CRM_STATUS_LABELS[item]} · {dash.counts[item] ?? 0}
              </button>
            ))}
          </div>
        ) : null}



        {(dash?.total ?? 0) > 0 ? (
          <div className="flex justify-end">
            <ConfirmDelete
              label="Elimina tutta la pipeline"
              warning="Verranno eliminate TUTTE le aziende con audit, punteggi, proposte, note, attività e tutte le discovery."
              requireText="ELIMINA"
              pending={purge.isPending}
              onConfirm={() => purge.mutate(deleteAllCompanies)}
            />
          </div>
        ) : null}
        {purgeError ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{purgeError}</p> : null}

        {categoriesQuery.isError ? (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            Impossibile caricare i settori.
            <button type="button" className="ml-2 underline" onClick={() => void categoriesQuery.refetch()}>Riprova</button>
          </p>
        ) : null}
        <form onSubmit={(event) => event.preventDefault()} className="grid gap-3 rounded-2xl border border-stone-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
          <input
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder="Cerca azienda"
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
          <input
            value={city}
            onChange={(event) => setCity(event.target.value)}
            placeholder="Città"
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          >
            <option value="">{categoriesQuery.isPending ? "Caricamento settori…" : "Settore (tutti)"}</option>
            {category && !categoriesQuery.data?.some((item) => item.value === category) ? (
              <option value={category}>{category} ({categoriesQuery.isSuccess ? "0" : "…"})</option>
            ) : null}
            {(categoriesQuery.data ?? []).map((item) => (
              <option key={item.value} value={item.value}>
                {item.label} ({item.count})
              </option>
            ))}
          </select>
          <input
            value={tag}
            onChange={(event) => setTag(event.target.value)}
            placeholder="Tag"
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
          <select
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          >
            <option value="">Priorità (tutte)</option>
            {PRIORITIES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <input
            type="number"
            min={0}
            max={100}
            value={minScore}
            onChange={(event) => setMinScore(event.target.value)}
            placeholder="Punteggio min"
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
          <label className="flex items-center gap-2 text-sm text-stone-700">
            <input type="checkbox" checked={shortlist} onChange={(event) => setShortlist(event.target.checked)} />
            Solo shortlist
          </label>
          <label className="flex items-center gap-2 text-sm text-stone-700">
            <input type="checkbox" checked={favorite} onChange={(event) => setFavorite(event.target.checked)} />
            Solo preferiti
          </label>
          <label className="flex items-center gap-2 text-sm text-stone-700">
            <input
              type="checkbox"
              checked={contactableOnly}
              onChange={(event) => setContactableOnly(event.target.checked)}
            />
            Nascondi incontattabili
          </label>
        </form>

        <section className="space-y-3">
          <div className="flex items-center gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={allSelected} disabled={!rows.length || listQuery.isFetching}
                ref={(node) => { if (node) node.indeterminate = selectedRows.length > 0 && !allSelected; }}
                onChange={(event) => setSelection({ key: filterKey, ids: event.target.checked ? rows.map((item) => item.company_id) : [] })} />
              Seleziona tutti i risultati della ricerca ({rows.length})
            </label>
            <span>{selectedRows.length} selezionate</span>
          </div>
          <BulkEnrichPanel selection={{
            withWebsite: selectedRows.filter((item) => item.has_website).map((item) => item.company_id),
            withoutWebsite: selectedRows.filter((item) => !item.has_website).map((item) => item.company_id),
          }} />
        </section>

        <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-stone-50 text-xs tracking-wide text-stone-500 uppercase">
              <tr>
                <th className="px-4 py-3">Seleziona</th>
                <th className="px-4 py-3">Azienda</th>
                <th className="px-4 py-3">Stato</th>
                <th className="px-4 py-3">Segmento</th>
                <th className="px-4 py-3">Punteggio</th>
                <th className="px-4 py-3">Priorità</th>
                <th className="px-4 py-3">Tag</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {(listQuery.data ?? []).map((item) => {
                const isGreenfield = item.segment === "greenfield";
                const score = isGreenfield ? item.growth_score : item.opportunity_score;
                const priority = isGreenfield ? item.growth_priority : item.priority;
                return (
                  <tr key={item.id} className="border-t border-stone-100">
                    <td className="px-4 py-3">
                      <input type="checkbox" aria-label={`Seleziona ${item.company_name}`}
                        checked={selectedIds.includes(item.company_id)} disabled={listQuery.isFetching}
                        onChange={(event) => toggleRow(item.company_id, event.target.checked)} />
                    </td>
                    <td className="px-4 py-3">
                      <Link to={`/companies/${item.company_id}`} className="font-medium hover:underline">
                        {item.is_favorite ? "★ " : ""}
                        {item.company_name}
                      </Link>
                      <p className="text-xs text-stone-500">
                        {[item.city, item.category].filter(Boolean).join(" · ") || item.domain || "—"}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-stone-600">{CRM_STATUS_LABELS[item.status] ?? item.status}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          isGreenfield ? "bg-amber-100 text-amber-800" : "bg-stone-100 text-stone-700"
                        }`}
                      >
                        {isGreenfield ? "Da creare" : "Da rifare"}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-medium">
                      {score ?? "—"}
                      {isGreenfield && score != null ? (
                        <span className="ml-1 text-xs font-normal text-stone-500">(growth)</span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3">
                      {!isGreenfield && item.latest_audit_id ? (
                        <Link to={`/audits/${item.latest_audit_id}`} className="underline">
                          {priority ?? "audit"}
                        </Link>
                      ) : (
                        <span className="text-stone-500">{priority ?? "—"}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-stone-500">{item.tags.map((tagItem) => tagItem.name).join(", ") || "—"}</td>
                    <td className="px-4 py-3">
                      <ConfirmDelete
                        label="Elimina"
                        warning={`Verrà eliminata ${item.company_name} con audit, punteggi, proposte, note e attività.`}
                        pending={purge.isPending}
                        onConfirm={() => purge.mutate(() => deleteCompany(item.company_id))}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {listQuery.isSuccess && (listQuery.data?.length ?? 0) === 0 ? (
            <p className="px-4 py-6 text-sm text-stone-500">Nessuna opportunità con questi filtri.</p>
          ) : null}
        </div>
      </main>
  );
}

function Stat({
  label,
  value,
  onClick,
}: {
  label: string;
  value: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-2xl border border-stone-200 bg-white px-4 py-3 text-left hover:border-stone-400"
    >
      <p className="text-xs tracking-wide text-stone-500 uppercase">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </button>
  );
}

