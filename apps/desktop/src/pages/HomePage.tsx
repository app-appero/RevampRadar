import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { createAudit, fetchRecentAudits } from "../api/audits";
import { fetchRecentDiscoveries } from "../api/discovery";
import { fetchDashboard } from "../api/crm";
import { ApiError } from "../api/health";
import { deleteAllAudits, deleteAllDiscoveries, deleteAudit, deleteDiscovery } from "../api/purge";
import { ConfirmDelete } from "../components/ConfirmDelete";

export function HomePage() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const auditsQuery = useQuery({
    queryKey: ["recent-audits"],
    queryFn: () => fetchRecentAudits(8),
    refetchInterval: (query) =>
      query.state.data?.some((item) => item.status === "queued" || item.status === "running")
        ? 2000
        : false,
  });
  const discoveriesQuery = useQuery({
    queryKey: ["recent-discoveries"],
    queryFn: () => fetchRecentDiscoveries(6),
    refetchInterval: (query) =>
      query.state.data?.some((item) => item.status === "queued" || item.status === "running")
        ? 2000
        : false,
  });
  const purge = useMutation({
    mutationFn: (action: () => Promise<number>) => action(),
    onMutate: () => setError(null),
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Eliminazione non riuscita.");
    },
  });
  const dashboardQuery = useQuery({
    queryKey: ["crm-dashboard"],
    queryFn: fetchDashboard,
  });

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const audit = await createAudit(url);
      navigate(`/audits/${audit.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Analisi non avviata.");
    } finally {
      setSubmitting(false);
    }
  }

  const dash = dashboardQuery.data;

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-10 px-6 py-12">
      <header className="space-y-2">
        <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">
          Single Website Analyzer
        </p>
        <h1 className="text-4xl font-semibold tracking-tight">Analizza un sito</h1>
        <p className="max-w-xl text-stone-600">
          Inserisci un URL. RevampRadar produce un audit tecnico, screenshot,
          Website Score e un Opportunity Score spiegabile.
        </p>
      </header>

      <form
        onSubmit={(event) => void onSubmit(event)}
        className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm"
      >
        <label htmlFor="url" className="text-sm font-medium text-stone-700">
          URL del sito
        </label>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row">
          <input
            id="url"
            name="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="es. hotel-esempio.it"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
            disabled={submitting}
            autoFocus
          />
          <button
            type="submit"
            disabled={submitting || url.trim().length === 0}
            className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium whitespace-nowrap text-white hover:bg-stone-800 disabled:opacity-50"
          >
            {submitting ? "Avvio…" : "Avvia analisi"}
          </button>
        </div>
        {error ? (
          <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
        ) : null}
      </form>

      {dash ? (
        <section className="grid gap-3 sm:grid-cols-3">
          <Stat to="/pipeline" label="Opportunità" value={dash.total} />
          <Stat to="/pipeline" label="Da contattare" value={dash.to_contact} />
          <Stat to="/pipeline" label="Alta priorità" value={dash.high_priority} />
        </section>
      ) : null}

      <section className="grid gap-8 lg:grid-cols-2">
        <div>
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-lg font-medium">Audit recenti</h2>
            {(auditsQuery.data?.length ?? 0) > 0 ? (
              <ConfirmDelete
                label="Elimina tutti"
                warning="Verranno eliminati TUTTI gli audit (punteggi, problemi, screenshot e proposte collegate). Le aziende restano nella pipeline."
                requireText="ELIMINA"
                pending={purge.isPending}
                onConfirm={() => purge.mutate(deleteAllAudits)}
              />
            ) : null}
          </div>
          <p className="mt-1 text-sm text-stone-500">Riprendi un’analisi senza perdere il filo.</p>
          <ul className="mt-4 space-y-2">
            {(auditsQuery.data ?? []).map((audit) => (
              <li key={audit.id} className="space-y-2">
                <Link
                  to={`/audits/${audit.id}`}
                  className="flex items-baseline justify-between gap-3 rounded-xl border border-stone-200 bg-white px-4 py-3 hover:border-stone-400"
                >
                  <span>
                    <span className="font-medium">{audit.domain}</span>
                    <span className="ml-2 text-xs text-stone-500">
                      {audit.status === "queued" || audit.status === "running"
                        ? `${audit.progress_percent ?? 0}%`
                        : audit.status}
                    </span>
                  </span>
                  <span className="text-sm text-stone-600">
                    {audit.opportunity_score != null ? `Opp. ${audit.opportunity_score}` : "—"}
                  </span>
                </Link>
                <div className="flex justify-end">
                  <ConfirmDelete
                    label="Elimina"
                    warning={`Verrà eliminato l'audit di ${audit.domain} con punteggi, problemi, screenshot e proposta.`}
                    pending={purge.isPending}
                    onConfirm={() => purge.mutate(() => deleteAudit(audit.id))}
                  />
                </div>
              </li>
            ))}
          </ul>
          {auditsQuery.isSuccess && (auditsQuery.data?.length ?? 0) === 0 ? (
            <p className="mt-3 text-sm text-stone-500">Nessun audit ancora. Analizza un URL sopra.</p>
          ) : null}
        </div>
        <div>
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-lg font-medium">Discovery recenti</h2>
            {(discoveriesQuery.data?.length ?? 0) > 0 ? (
              <ConfirmDelete
                label="Elimina tutte"
                warning="Verranno eliminate TUTTE le discovery e le aziende trovate da loro, con audit, proposte, note e attività."
                requireText="ELIMINA"
                pending={purge.isPending}
                onConfirm={() => purge.mutate(deleteAllDiscoveries)}
              />
            ) : null}
          </div>
          <p className="mt-1 text-sm text-stone-500">
            <Link to="/discovery" className="underline hover:text-stone-900">
              Nuova ricerca
            </Link>
          </p>
          <ul className="mt-4 space-y-2">
            {(discoveriesQuery.data ?? []).map((run) => (
              <li key={run.id} className="space-y-2">
                <Link
                  to={`/discoveries/${run.id}`}
                  className="flex items-baseline justify-between gap-3 rounded-xl border border-stone-200 bg-white px-4 py-3 hover:border-stone-400"
                >
                  <span>
                    <span className="font-medium">
                      {run.industry} — {run.location}
                    </span>
                    <span className="ml-2 text-xs text-stone-500">
                      {run.status === "queued" || run.status === "running"
                        ? `${run.progress_percent ?? 0}%`
                        : run.status}
                    </span>
                  </span>
                  <span className="text-sm text-stone-600">{run.total_found} aziende</span>
                </Link>
                <div className="flex justify-end">
                  <ConfirmDelete
                    label="Elimina"
                    warning={`Verrà eliminata la ricerca "${run.industry} — ${run.location}" e le aziende trovate solo da questa, con audit, proposte, note e attività. Le aziende presenti anche in altre ricerche restano.`}
                    pending={purge.isPending}
                    onConfirm={() => purge.mutate(() => deleteDiscovery(run.id))}
                  />
                </div>
              </li>
            ))}
          </ul>
          {discoveriesQuery.isSuccess && (discoveriesQuery.data?.length ?? 0) === 0 ? (
            <p className="mt-3 text-sm text-stone-500">Nessuna discovery ancora.</p>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function Stat({ to, label, value }: { to: string; label: string; value: number }) {
  return (
    <Link
      to={to}
      className="rounded-2xl border border-stone-200 bg-white px-4 py-3 hover:border-stone-400"
    >
      <p className="text-xs tracking-wide text-stone-500 uppercase">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </Link>
  );
}
