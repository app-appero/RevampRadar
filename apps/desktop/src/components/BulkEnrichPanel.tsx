import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchEnrichCandidates,
  cancelEnrichment,
  fetchEnrichJob,
  startEnrichment,
  type EnrichJob,
  type EnrichKind,
} from "../api/enrichment";
import { ApiError } from "../api/health";

const LABELS: Record<EnrichKind, { idle: string; running: string; hint: string }> = {
  analysis: { idle: "Analizza siti", running: "Analisi siti…", hint: "Analizza solo i siti delle aziende selezionate" },
  city: {
    idle: "Recupera città",
    running: "Recupero città…",
    hint: "Chiede a OpenStreetMap la città delle aziende che non ce l'hanno (circa 1 al secondo)",
  },
  places: {
    idle: "Recupera solo non visti",
    running: "Verifica su Google…",
    hint: "Cerca su Google Places sito e telefono delle aziende senza sito (richiede la chiave in Impostazioni)",
  },
};

export function BulkEnrichPanel({
  selection,
}: {
  selection?: { withWebsite: string[]; unseenWithoutWebsite: string[] };
}) {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const candidates = useQuery({ queryKey: ["enrich-candidates"], queryFn: fetchEnrichCandidates });
  const job = useQuery({
    queryKey: ["enrich-job", jobId],
    queryFn: () => fetchEnrichJob(jobId!),
    enabled: jobId !== null,
    refetchInterval: (query) => (["running", "cancelling"].includes(query.state.data?.status ?? "") ? 1000 : false),
  });
  const current: EnrichJob | undefined = job.data;
  const running = current?.status === "running" || current?.status === "cancelling";

  const start = useMutation({
    mutationFn: (kind: EnrichKind) => startEnrichment(
      kind,
      selection ? (kind === "analysis" ? selection.withWebsite : selection.unseenWithoutWebsite) : undefined,
    ),
    onSuccess: (started) => {
      setError(null);
      setJobId(started.id);
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Recupero non avviato.");
    },
  });

  const cancel = useMutation({
    mutationFn: () => cancelEnrichment(jobId!),
    onSuccess: (cancelled) => queryClient.setQueryData(["enrich-job", jobId], cancelled),
    onError: () => setError("Impossibile annullare: il backend potrebbe non supportare l'arresto dei job precedenti."),
  });
  const finished = current && !running;
  useEffect(() => {
    if (!finished) return;
    void queryClient.invalidateQueries({ queryKey: ["opportunities"] });
    void queryClient.invalidateQueries({ queryKey: ["crm-dashboard"] });
    void queryClient.invalidateQueries({ queryKey: ["enrich-candidates"] });
  }, [finished, queryClient]);

  const counts: Record<EnrichKind, number | undefined> = {
    city: candidates.data?.missing_city,
    places: selection ? selection.unseenWithoutWebsite.length : candidates.data?.missing_website,
    analysis: selection?.withWebsite.length ?? 0,
  };
  const percent = current && current.total > 0 ? Math.round((current.processed / current.total) * 100) : 0;

  return (
    <section className="space-y-3 rounded-2xl border border-stone-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        {((selection ? ["analysis", "places"] : ["city", "places"]) as EnrichKind[]).map((kind) => (
          <button
            key={kind}
            type="button"
            disabled={running || (jobId !== null && !current) || start.isPending || counts[kind] === 0}
            onClick={() => start.mutate(kind)}
            title={LABELS[kind].hint}
            className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50 disabled:opacity-50"
          >
            {running && current?.kind === kind ? LABELS[kind].running : LABELS[kind].idle}
            {counts[kind] != null ? ` (${counts[kind]})` : ""}
          </button>
        ))}
        {running ? (
          <button type="button" disabled={cancel.isPending || current?.status === "cancelling"}
            onClick={() => cancel.mutate()}
            className="rounded-lg border border-red-300 px-4 py-2 text-sm text-red-700 disabled:opacity-50">
            {current?.status === "cancelling" ? "Annullamento…" : "Annulla ricerca"}
          </button>
        ) : null}
      </div>
      {current?.status === "cancelling" ? <p className="text-sm text-stone-600">Attendo la chiamata in corso. Non verranno avviate altre aziende.</p> : null}

      {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}

      {current ? (
        <div className="space-y-1">
          <div className="h-2 w-full overflow-hidden rounded-full bg-stone-100">
            <div
              className={`h-full transition-all ${current.status === "failed" ? "bg-red-500" : "bg-stone-900"}`}
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="text-xs text-stone-600">
            {current.processed}/{current.total} · riuscite {current.updated} · non trovate {current.not_found}
            {current.failed > 0 ? ` · errori ${current.failed}` : ""}
            {current.status === "completed" ? " · completato" : ""}
            {current.status === "failed" ? " · interrotto" : ""}
            {current.status === "cancelled" ? " · annullato" : ""}
          </p>
          {current.last_error ? (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{current.last_error}</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
