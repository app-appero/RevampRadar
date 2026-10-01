import { useIsFetching, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, Outlet } from "react-router-dom";

import { getApiMode, remoteAvailable, setApiMode } from "../api/apiTarget";
import { fetchHealth, getApiBaseUrl } from "../api/health";
import { HistoryNav } from "./HistoryNav";

const NAV_ITEMS = [
  { to: "/", label: "Analizza", end: true },
  { to: "/discovery", label: "Discovery", end: false },
  { to: "/map", label: "Mappa", end: false },
  { to: "/pipeline", label: "Pipeline", end: false },
  { to: "/agenda", label: "Agenda", end: false },
  { to: "/settings", label: "Impostazioni", end: false },
] as const;

export function AppShell() {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  });
  const connected = healthQuery.data?.status === "ok";
  const queryClient = useQueryClient();
  const refreshing = useIsFetching({ predicate: (query) => query.queryKey[0] !== "health" }) > 0;
  const remote = getApiMode() === "remote";

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-56 shrink-0 flex-col justify-between border-r border-stone-200 bg-white px-4 py-5">
        <div className="space-y-6">
          <div className="space-y-3">
            <Link to="/" className="block text-lg font-semibold tracking-tight">
              RevampRadar
            </Link>
            <HistoryNav />
          </div>
          <nav className="flex flex-col gap-1 text-sm">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 font-medium ${
                    isActive ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="space-y-3 text-xs text-stone-500">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate" title={getApiBaseUrl()}>
              {remote ? "Backend remoto" : "Backend locale"}
            </span>
            <span
              className={`rounded-full px-2 py-0.5 font-medium ${
                connected ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-600"
              }`}
            >
              {connected ? "API ok" : "API"}
            </span>
          </div>
          <p className="truncate" title={getApiBaseUrl()}>
            {getApiBaseUrl()}
          </p>
          <button
            type="button"
            disabled={refreshing}
            onClick={() => void queryClient.invalidateQueries()}
            title="Ricarica dal server i dati di tutte le schermate"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-50"
          >
            {refreshing ? "Aggiorno…" : "Aggiorna"}
          </button>
          {remoteAvailable() ? (
            <button
              type="button"
              onClick={() => setApiMode(remote ? "local" : "remote")}
              title="Passa tra backend locale e backend remoto (Railway)"
              className="w-full rounded-lg border border-stone-300 px-3 py-2 font-medium text-stone-700 hover:bg-stone-50"
            >
              {remote ? "Remoto → Locale" : "Locale → Remoto"}
            </button>
          ) : null}
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  );
}
