import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { fetchHealth, getApiBaseUrl } from "../api/health";

export function AppShell({ children }: { children: ReactNode }) {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  });
  const connected = healthQuery.data?.status === "ok";

  return (
    <div className="min-h-screen">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            RevampRadar
          </Link>
          <div className="flex items-center gap-4">
            <nav className="flex items-center gap-3 text-sm">
              <Link to="/" className="text-stone-600 hover:text-stone-900">
                Analizza
              </Link>
              <Link to="/discovery" className="text-stone-600 hover:text-stone-900">
                Discovery
              </Link>
            </nav>
            <div className="flex items-center gap-3 text-sm text-stone-500">
              <span className="hidden sm:inline">{getApiBaseUrl()}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  connected
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-stone-100 text-stone-600"
                }`}
              >
                {connected ? "API ok" : "API"}
              </span>
            </div>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}
