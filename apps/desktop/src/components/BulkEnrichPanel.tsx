import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchEnrichCandidates,
  fetchEnrichJob,
  startEnrichment,
  type EnrichJob,
  type EnrichKind,
} from "../api/enrichment";
import { ApiError } from "../api/health";

const LABELS: Record<EnrichKind, { idle: string; running: string; hint: string }> = {
  city: {
    idle: "Recupera città",
    running: "Recupero città…",
    hint: "Chiede a OpenStreetMap la città delle aziende che non ce l'hanno (circa 1 al secondo)",
  },
  places: {
    idle: "Recupera sito e telefono",
    running: "Verifica su Google…",
    hint: "Cerca su Google Places sito e telefono delle aziende senza sito (richiede la chiave in Impostazioni)",
  },
};

export function BulkEnrichPanel() {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const candidates = useQuery({ queryKey: ["enrich-candidates"], queryFn: fetchEnrichCandidates });
  const job = useQuery({
    queryKey: ["enrich-job", jobId],
    queryFn: () => fetchEnrichJob(jobId!),
    enabled: jobId !== null,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 1000 : false),
  });
  const current: EnrichJob | undefined = job.data;
  const running = current?.status === "running";

  const start = useMutation({
    mutationFn: (kind: EnrichKind) => startEnrichment(kind),
    onSuccess: (started) => {
      setError(null);
      setJobId(started.id);
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Recupero non avviato.");
    },
  });

  const finished = current && current.status !== "running";
  useEffect(() => {
    if (!finished) return;
    void queryClient.invalidateQueries({ queryKey: ["opportunities"] });
    void queryClient.invalidateQueries({ queryKey: ["crm-dashboard"] });
    void queryClient.invalidateQueries({ queryKey: ["enrich-candidates"] });
  }, [finished, queryClient]);

  const counts: Record<EnrichKind, number | undefined> = {
    city: candidates.data?.missing_city,
    places: candidates.data?.missing_website,
  };
  const percent = current && current.total > 0 ? Math.round((current.processed / current.total) * 100) : 0;

  return (
    <section className="space-y-3 rounded-2xl border border-stone-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        {(Object.keys(LABELS) as EnrichKind[]).map((kind) => (
          <button
            key={kind}
            type="button"
            disabled={running || start.isPending || counts[kind] === 0}
            onClick={() => start.mutate(kind)}
            title={LABELS[kind].hint}
            className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50 disabled:opacity-50"
          >
            {running && current?.kind === kind ? LABELS[kind].running : LABELS[kind].idle}
            {counts[kind] != null ? ` (${counts[kind]})` : ""}
          </button>
        ))}
      </div>

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
            {current.processed}/{current.total} · aggiornate {current.updated} · non trovate {current.not_found}
            {current.failed > 0 ? ` · errori ${current.failed}` : ""}
            {current.status === "completed" ? " · completato" : ""}
            {current.status === "failed" ? " · interrotto" : ""}
          </p>
          {current.last_error ? (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{current.last_error}</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
