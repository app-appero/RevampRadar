import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  enrichFromRegistry,
  fetchBusinessSignals,
  fetchCompanyResearch,
  saveBusinessSignal,
  deleteBusinessSignal,
  startCompanyResearch,
  RESEARCH_STATUS_LABELS,
  type BusinessSignalInput,
} from "../api/deepResearch";
import { ApiError } from "../api/health";
import { ExternalLink } from "./ExternalLink";

const CHANNEL_LABELS: Record<string, string> = {
  website: "Sito",
  instagram: "Instagram",
  facebook: "Facebook",
  tiktok: "TikTok",
  youtube: "YouTube",
  linkedin: "LinkedIn",
  app_store: "App Store",
  google_play: "Google Play",
};

export function DeepResearchPanel({ companyId }: { companyId: string }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [showSignalForm, setShowSignalForm] = useState(false);
  const [registryVat, setRegistryVat] = useState("");
  const [registryError, setRegistryError] = useState<string | null>(null);

  const researchQuery = useQuery({
    queryKey: ["company-research", companyId],
    queryFn: () => fetchCompanyResearch(companyId),
    refetchInterval: (query) => (query.state.data?.status === "in_progress" ? 1500 : false),
  });

  const signalsQuery = useQuery({
    queryKey: ["business-signals", companyId],
    queryFn: () => fetchBusinessSignals(companyId),
  });

  const start = useMutation({
    mutationFn: () => startCompanyResearch(companyId),
    onSuccess: (data) => {
      setError(null);
      queryClient.setQueryData(["company-research", companyId], data);
      void queryClient.invalidateQueries({ queryKey: ["company-research", companyId] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Ricerca non avviata."),
  });

  const saveSignal = useMutation({
    mutationFn: (payload: BusinessSignalInput) => saveBusinessSignal(companyId, payload),
    onSuccess: () => {
      setShowSignalForm(false);
      void queryClient.invalidateQueries({ queryKey: ["business-signals", companyId] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Segnale non salvato."),
  });

  const registry = useMutation({
    mutationFn: () => enrichFromRegistry(companyId, registryVat.trim() || undefined),
    onSuccess: () => {
      setRegistryError(null);
      void queryClient.invalidateQueries({ queryKey: ["business-signals", companyId] });
    },
    onError: (err) =>
      setRegistryError(err instanceof ApiError ? err.message : "Recupero dati aziendali non riuscito."),
  });

  const removeSignal = useMutation({
    mutationFn: (signalId: string) => deleteBusinessSignal(companyId, signalId),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["business-signals", companyId] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Segnale non eliminato."),
  });

  const research = researchQuery.data;
  const brief = research?.brief;
  const status = research?.status ?? "never";
  const canStart = status !== "in_progress";

  return (
    <section className="space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-medium">Approfondimento prospect</h2>
          <p className="text-sm text-stone-500">
            Secondo livello di ricerca, solo su richiesta: sito, presenza digitale, segnali
            aziendali. Stato: <span className="font-medium">{RESEARCH_STATUS_LABELS[status]}</span>
            {research?.completed_at ? ` · ${new Date(research.completed_at).toLocaleString()}` : ""}
          </p>
        </div>
        <button
          type="button"
          disabled={!canStart || start.isPending}
          onClick={() => {
            setError(null);
            start.mutate();
          }}
          className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
        >
          {status === "in_progress" ? "Ricerca in corso…" : status === "never" ? "Approfondisci prospect" : "Aggiorna approfondimento"}
        </button>
      </div>

      {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}

      {brief ? (
        <div className="space-y-4">
          {brief.what_it_does ? (
            <div>
              <h3 className="text-xs tracking-wide text-stone-500 uppercase">Cosa fa</h3>
              <p className="mt-1 text-sm text-stone-700">{brief.what_it_does}</p>
            </div>
          ) : null}

          {brief.value_elements.length > 0 ? (
            <div>
              <h3 className="text-xs tracking-wide text-stone-500 uppercase">Punti di forza emersi</h3>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-stone-700">
                {brief.value_elements.map((item) => (
                  <li key={item.label}>{item.label}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div>
            <h3 className="text-xs tracking-wide text-stone-500 uppercase">Presenza digitale</h3>
            <div className="mt-1 flex flex-wrap gap-2">
              {Object.entries(brief.digital_presence.channels).map(([name, item]) => (
                <span
                  key={name}
                  className={`rounded-full px-3 py-1 text-xs ${
                    item.found ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-400"
                  }`}
                >
                  {item.found && item.url ? (
                    <ExternalLink href={item.url}>{CHANNEL_LABELS[name] ?? name}</ExternalLink>
                  ) : (
                    CHANNEL_LABELS[name] ?? name
                  )}
                </span>
              ))}
            </div>
          </div>

          {brief.website_problems.length > 0 ? (
            <div>
              <h3 className="text-xs tracking-wide text-stone-500 uppercase">Problemi del sito rilevati</h3>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-stone-700">
                {brief.website_problems.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {brief.homepage_direction ? (
            <div>
              <h3 className="text-xs tracking-wide text-stone-500 uppercase">Possibile direzione homepage</h3>
              <p className="mt-1 text-sm text-stone-700">{brief.homepage_direction}</p>
            </div>
          ) : null}

          {brief.missing_information.length > 0 ? (
            <div>
              <h3 className="text-xs tracking-wide text-stone-500 uppercase">Informazioni mancanti</h3>
              <p className="mt-1 text-sm text-stone-500">{brief.missing_information.join(" · ")}</p>
            </div>
          ) : null}
        </div>
      ) : status === "never" ? (
        <p className="text-sm text-stone-500">
          Nessun approfondimento avviato. La Discovery e l'audit continuano a funzionare come sempre.
        </p>
      ) : null}

      <div className="space-y-2 border-t border-stone-100 pt-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Business Signals</h3>
          <button
            type="button"
            onClick={() => setShowSignalForm((value) => !value)}
            className="text-sm text-stone-600 underline"
          >
            {showSignalForm ? "Annulla" : "Aggiungi segnale"}
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-2 rounded-xl bg-stone-50 px-3 py-2">
          <button
            type="button"
            disabled={registry.isPending}
            onClick={() => {
              setRegistryError(null);
              registry.mutate();
            }}
            className="rounded-lg bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
          >
            {registry.isPending ? "Ricerca in corso…" : "Recupera dati aziendali (Registro Imprese)"}
          </button>
          <input
            value={registryVat}
            onChange={(event) => setRegistryVat(event.target.value)}
            placeholder="P.IVA (facoltativa)"
            className="w-44 rounded-lg border border-stone-300 px-3 py-1.5 font-mono text-sm outline-none focus:border-stone-900"
          />
          <span className="text-xs text-stone-500">
            Cerca per nome e comune. Se non trova l'azienda, indica la P.IVA. Consuma crediti OpenAPI.com.
          </span>
        </div>
        {registryError ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{registryError}</p>
        ) : null}
        <ul className="space-y-2">
          {(signalsQuery.data ?? []).map((item) => (
            <li
              key={item.id}
              className="flex items-center justify-between rounded-xl border border-stone-200 px-3 py-2 text-sm"
            >
              <div>
                <p className="font-medium">
                  {item.label}
                  {item.period ? ` (${item.period})` : ""}: {item.value}
                  {item.unit ? ` ${item.unit}` : ""}
                </p>
                <p className="text-xs text-stone-500">
                  Fonte: {item.source} · {item.confidence}
                  {item.is_manual ? " · manuale" : ""}
                </p>
              </div>
              <button
                type="button"
                onClick={() => removeSignal.mutate(item.id)}
                className="text-xs text-stone-500 underline"
              >
                Elimina
              </button>
            </li>
          ))}
        </ul>
        {showSignalForm ? (
          <SignalForm onSave={(payload) => saveSignal.mutate(payload)} pending={saveSignal.isPending} />
        ) : null}
      </div>
    </section>
  );
}

function SignalForm({
  onSave,
  pending,
}: {
  onSave: (payload: BusinessSignalInput) => void;
  pending: boolean;
}) {
  const [key, setKey] = useState("employees");
  const [label, setLabel] = useState("Dipendenti");
  const [value, setValue] = useState("");
  const [period, setPeriod] = useState("");
  const [source, setSource] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!value.trim() || !source.trim()) return;
    onSave({ key, label, value: value.trim(), period: period.trim() || undefined, source: source.trim(), confidence: "manual" });
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-2 rounded-xl border border-stone-200 p-3 sm:grid-cols-2">
      <select
        value={key}
        onChange={(event) => {
          const next = event.target.value;
          setKey(next);
          setLabel(SIGNAL_LABELS[next] ?? next);
        }}
        className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
      >
        {Object.entries(SIGNAL_LABELS).map(([k, v]) => (
          <option key={k} value={k}>
            {v}
          </option>
        ))}
      </select>
      <input
        value={period}
        onChange={(event) => setPeriod(event.target.value)}
        placeholder="Anno/periodo (opzionale)"
        className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
      />
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Valore (es. 18, €2.300.000, SRL)"
        className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
      />
      <input
        value={source}
        onChange={(event) => setSource(event.target.value)}
        placeholder="Fonte (es. visura camerale, LinkedIn azienda)"
        className="rounded-lg border border-stone-300 px-3 py-2 text-sm sm:col-span-2"
      />
      <button
        type="submit"
        disabled={pending}
        className="w-fit rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 sm:col-span-2"
      >
        {pending ? "Salvataggio…" : "Salva segnale"}
      </button>
    </form>
  );
}

const SIGNAL_LABELS: Record<string, string> = {
  employees: "Dipendenti",
  revenue: "Fatturato",
  revenue_trend: "Trend fatturato",
  founding_year: "Anno di fondazione",
  legal_form: "Forma societaria",
};
