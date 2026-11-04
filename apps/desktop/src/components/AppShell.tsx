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
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="sticky top-0 z-10 flex w-full shrink-0 flex-col gap-3 border-b border-stone-200 bg-white px-4 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] md:h-screen md:w-56 md:justify-between md:border-r md:border-b-0 md:py-5">
        <div className="min-w-0 space-y-3 md:space-y-6">
          <div className="space-y-3">
            <Link to="/" className="block text-lg font-semibold tracking-tight">
              RevampRadar
            </Link>
            <span className="hidden md:block"><HistoryNav /></span>
          </div>
          <nav
            aria-label="Navigazione principale"
            className="fixed inset-x-0 bottom-0 z-20 flex border-t border-stone-200 bg-white px-1 pt-1.5 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] text-[11px] md:static md:z-auto md:flex-col md:gap-1 md:border-t-0 md:bg-transparent md:p-0 md:text-sm"
          >
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex min-h-11 flex-1 items-center justify-center rounded-lg px-1 text-center font-medium md:block md:flex-none md:px-3 md:py-2 md:text-left ${
                    isActive ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-2 text-xs text-stone-500 md:block md:space-y-3">
          <div className="flex flex-1 items-center justify-between gap-2">
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
          <p className="hidden truncate md:block" title={getApiBaseUrl()}>
            {getApiBaseUrl()}
          </p>
          <button
            type="button"
            disabled={refreshing}
            onClick={() => void queryClient.invalidateQueries()}
            title="Ricarica dal server i dati di tutte le schermate"
            className="rounded-lg border border-stone-300 px-3 py-2 font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-50 md:w-full"
          >
            {refreshing ? "Aggiorno…" : "Aggiorna"}
          </button>
          {remoteAvailable() ? (
            <button
              type="button"
              onClick={() => setApiMode(remote ? "local" : "remote")}
              title="Passa tra backend locale e backend remoto (Railway)"
              className="hidden w-full rounded-lg border border-stone-300 px-3 py-2 font-medium text-stone-700 hover:bg-stone-50 md:block"
            >
              {remote ? "Remoto → Locale" : "Locale → Remoto"}
            </button>
          ) : null}
        </div>
      </aside>
      <div className="min-w-0 flex-1 pb-20 md:pb-0">
        <Outlet />
      </div>
    </div>
  );
}
