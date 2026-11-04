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

const icon = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.9,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  "aria-hidden": true,
} as const;

// Tab bar mobile (come da canvas): Analizza, Discovery, Pipeline, Agenda, Mappa.
const TABS = [
  {
    to: "/",
    label: "Analizza",
    end: true,
    svg: (
      <svg {...icon}>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
      </svg>
    ),
  },
  {
    to: "/discovery",
    label: "Discovery",
    end: false,
    svg: (
      <svg {...icon}>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="4.5" />
        <path d="M12 12 18 6" />
      </svg>
    ),
  },
  {
    to: "/pipeline",
    label: "Pipeline",
    end: false,
    svg: (
      <svg {...icon}>
        <rect x="3" y="4" width="5" height="16" rx="1" />
        <rect x="10" y="4" width="5" height="10" rx="1" />
        <rect x="17" y="4" width="4" height="13" rx="1" />
      </svg>
    ),
  },
  {
    to: "/agenda",
    label: "Agenda",
    end: false,
    svg: (
      <svg {...icon}>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M3 10h18M8 3v4M16 3v4" />
      </svg>
    ),
  },
  {
    to: "/map",
    label: "Mappa",
    end: false,
    svg: (
      <svg {...icon}>
        <path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z" />
        <circle cx="12" cy="10" r="2.5" />
      </svg>
    ),
  },
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
      {/* Mobile: header con margine per notch/notifiche */}
      <header className="flex items-center justify-between gap-2 px-5 pb-1 pt-[calc(env(safe-area-inset-top)+1rem)] md:hidden">
        <Link to="/" className="text-xl font-semibold tracking-tight">
          RevampRadar
        </Link>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ${
              connected ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-600"
            }`}
          >
            {connected ? "API ok" : "API"}
          </span>
          <NavLink
            to="/settings"
            aria-label="Impostazioni"
            className={({ isActive }) =>
              `flex h-11 w-11 items-center justify-center rounded-xl ${isActive ? "bg-stone-900 text-white" : "text-stone-600"}`
            }
          >
            <svg {...icon}>
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
            </svg>
          </NavLink>
        </div>
      </header>

      {/* Mobile: tab bar in basso */}
      <nav
        aria-label="Navigazione principale"
        className="fixed inset-x-0 bottom-0 z-20 flex border-t border-stone-200 bg-white px-1 pt-1.5 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] md:hidden"
      >
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center gap-0.5 py-1 text-[11px] ${
                isActive ? "font-semibold text-stone-900" : "font-medium text-stone-600"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={`flex h-[30px] w-[52px] items-center justify-center rounded-full ${
                    isActive ? "bg-stone-900 text-white" : ""
                  }`}
                >
                  {tab.svg}
                </span>
                {tab.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Desktop: sidebar */}
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col justify-between border-r border-stone-200 bg-white px-4 py-5 md:flex">
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
      <div className="min-w-0 flex-1 pb-24 md:pb-0">
        <Outlet />
      </div>
    </div>
  );
}
