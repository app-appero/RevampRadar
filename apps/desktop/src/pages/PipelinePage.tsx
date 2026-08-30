import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  CRM_STATUSES,
  CRM_STATUS_LABELS,
  fetchDashboard,
  fetchOpportunities,
  type OpportunityFilters,
} from "../api/crm";

const PRIORITIES = ["VERY_HIGH", "HIGH", "MEDIUM", "LOW"] as const;

export function PipelinePage() {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [city, setCity] = useState("");
  const [category, setCategory] = useState("");
  const [tag, setTag] = useState("");
  const [priority, setPriority] = useState("");
  const [minScore, setMinScore] = useState("");
  const [shortlist, setShortlist] = useState(false);
  const [favorite, setFavorite] = useState(false);

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
    }),
    [status, q, city, category, tag, priority, minScore, shortlist, favorite],
  );

  const dashboardQuery = useQuery({
    queryKey: ["crm-dashboard"],
    queryFn: fetchDashboard,
  });
  const listQuery = useQuery({
    queryKey: ["opportunities", filters],
    queryFn: () => fetchOpportunities(filters),
  });
  const dash = dashboardQuery.data;

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

        <form className="grid gap-3 rounded-2xl border border-stone-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
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
          <input
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            placeholder="Settore"
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
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
            placeholder="Opportunity min"
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
        </form>

        <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-stone-50 text-xs tracking-wide text-stone-500 uppercase">
              <tr>
                <th className="px-4 py-3">Azienda</th>
                <th className="px-4 py-3">Stato</th>
                <th className="px-4 py-3">Opportunity</th>
                <th className="px-4 py-3">Priorità</th>
                <th className="px-4 py-3">Tag</th>
              </tr>
            </thead>
            <tbody>
              {(listQuery.data ?? []).map((item) => (
                <tr key={item.id} className="border-t border-stone-100">
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
                  <td className="px-4 py-3 font-medium">{item.opportunity_score ?? "—"}</td>
                  <td className="px-4 py-3">
                    {item.latest_audit_id ? (
                      <Link to={`/audits/${item.latest_audit_id}`} className="underline">
                        {item.priority ?? "audit"}
                      </Link>
                    ) : (
                      <span className="text-stone-500">{item.priority ?? "—"}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-stone-500">{item.tags.map((tagItem) => tagItem.name).join(", ") || "—"}</td>
                </tr>
              ))}
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

