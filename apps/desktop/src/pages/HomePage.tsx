import { useQuery } from "@tanstack/react-query";

import { fetchHealth, getApiBaseUrl } from "../api/health";

export function HomePage() {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 10_000,
  });

  const health = healthQuery.data;
  const isConnected = health?.status === "ok";
  const isDegraded = health?.status === "degraded";

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-8 px-6 py-12">
      <header className="space-y-2">
        <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">
          Foundation
        </p>
        <h1 className="text-4xl font-semibold tracking-tight">RevampRadar</h1>
        <p className="max-w-xl text-stone-600">
          Client desktop collegato al backend. Lo stato sotto conferma che API e
          database sono raggiungibili.
        </p>
      </header>

      <section className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-medium">Stato backend</h2>
            <p className="mt-1 text-sm text-stone-500">{getApiBaseUrl()}</p>
          </div>
          <StatusBadge
            loading={healthQuery.isLoading}
            connected={isConnected}
            degraded={isDegraded}
          />
        </div>

        {healthQuery.isError ? (
          <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            {healthQuery.error instanceof Error
              ? healthQuery.error.message
              : "Errore sconosciuto"}
          </p>
        ) : null}

        {health ? (
          <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
            <Info label="Servizio" value={health.service} />
            <Info label="Versione" value={health.version} />
            <Info label="Ambiente" value={health.environment} />
            <Info
              label="Database"
              value={health.database === "ok" ? "raggiungibile" : "non disponibile"}
            />
          </dl>
        ) : null}

        <button
          type="button"
          onClick={() => void healthQuery.refetch()}
          className="mt-6 rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800"
        >
          Aggiorna stato
        </button>
      </section>
    </main>
  );
}

function StatusBadge({
  loading,
  connected,
  degraded,
}: {
  loading: boolean;
  connected: boolean;
  degraded: boolean;
}) {
  if (loading) {
    return <Badge className="bg-stone-100 text-stone-600">verifica…</Badge>;
  }
  if (connected) {
    return <Badge className="bg-emerald-100 text-emerald-800">connesso</Badge>;
  }
  if (degraded) {
    return <Badge className="bg-amber-100 text-amber-800">degradato</Badge>;
  }
  return <Badge className="bg-red-100 text-red-800">offline</Badge>;
}

function Badge({
  className,
  children,
}: {
  className: string;
  children: string;
}) {
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${className}`}>
      {children}
    </span>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-stone-500">{label}</dt>
      <dd className="mt-1 font-medium">{value}</dd>
    </div>
  );
}
