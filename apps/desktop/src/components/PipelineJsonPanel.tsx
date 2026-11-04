import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  exportOpportunities,
  importOpportunities,
  type OpportunityFilters,
  type PipelineImportResult,
} from "../api/crm";
import { ApiError } from "../api/health";

function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// Esporta le aziende filtrate in JSON (per GPT) e reimporta il file arricchito.
export function PipelineJsonPanel({ filters }: { filters: OpportunityFilters }) {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const exporter = useMutation({
    mutationFn: () => exportOpportunities(filters),
    onMutate: () => {
      setError(null);
      setResult(null);
      setMessage(null);
    },
    onSuccess: (data) => {
      const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
      downloadJson(data, `revampradar-pipeline-${stamp}.json`);
      setMessage(`Esportate ${data.total} aziende.`);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Esportazione non riuscita."),
  });

  const importer = useMutation({
    mutationFn: async (file: File) => {
      let payload: unknown;
      try {
        payload = JSON.parse(await file.text());
      } catch {
        throw new ApiError("Il file non è un JSON valido.");
      }
      return importOpportunities(payload);
    },
    onMutate: () => {
      setError(null);
      setResult(null);
      setMessage(null);
    },
    onSuccess: (data) => {
      setResult(data);
      void queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      void queryClient.invalidateQueries({ queryKey: ["crm-dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["companies"] });
      void queryClient.invalidateQueries({ queryKey: ["company-opportunity"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Importazione non riuscita."),
  });

  const buttonClass =
    "h-10 rounded-xl border border-stone-300 bg-white px-4 text-sm font-semibold text-stone-700 hover:border-stone-500 disabled:opacity-50";

  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className={buttonClass} disabled={exporter.isPending} onClick={() => exporter.mutate()}>
          {exporter.isPending ? "Esporto…" : "Esporta JSON (filtro attuale)"}
        </button>
        <button type="button" className={buttonClass} disabled={importer.isPending} onClick={() => fileInput.current?.click()}>
          {importer.isPending ? "Importo…" : "Importa JSON"}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) importer.mutate(file);
          }}
        />
      </div>
      {message ? <p className="text-sm text-stone-600">{message}</p> : null}
      {error ? <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}
      {result ? (
        <div role="status" className="rounded-lg bg-stone-50 px-3 py-2 text-sm text-stone-700">
          <p>
            Import completato: {result.updated} aggiornate, {result.unchanged} invariate
            {result.errors.length ? `, ${result.errors.length} con errori` : ""}.
          </p>
          {result.errors.length ? (
            <ul className="mt-1 list-disc pl-5 text-red-800">
              {result.errors.slice(0, 10).map((item, index) => (
                <li key={`${item.company}-${index}`}>{item.company}: {item.error}</li>
              ))}
              {result.errors.length > 10 ? <li>… e altri {result.errors.length - 10}</li> : null}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
