import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  conceptFileUrl,
  deleteConcept,
  fetchConcepts,
  fetchDesignBrief,
  generateConcept,
  regenerateDesignBrief,
  updateDesignBrief,
  type DesignBrief,
  type DesignBriefInput,
} from "../api/concept";
import { ApiError } from "../api/health";

const SOURCE_LABELS: Record<string, string> = {
  deterministic: "concept generato",
  template: "concept generato",
  ai: "concept generato (AI)",
};

export function ConceptPanel({ companyId }: { companyId: string }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const briefQuery = useQuery({
    queryKey: ["design-brief", companyId],
    queryFn: () => fetchDesignBrief(companyId),
  });
  const conceptsQuery = useQuery({
    queryKey: ["concepts", companyId],
    queryFn: () => fetchConcepts(companyId),
  });

  const generate = useMutation({
    mutationFn: () => generateConcept(companyId),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["concepts", companyId] });
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Concept non generato."),
  });

  const remove = useMutation({
    mutationFn: (conceptId: string) => deleteConcept(companyId, conceptId),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["concepts", companyId] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Concept non eliminato."),
  });

  const saveBrief = useMutation({
    mutationFn: (payload: DesignBriefInput) => updateDesignBrief(companyId, payload),
    onSuccess: () => {
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: ["design-brief", companyId] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Design brief non salvato."),
  });

  const resetBrief = useMutation({
    mutationFn: () => regenerateDesignBrief(companyId),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["design-brief", companyId] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Design brief non rigenerato."),
  });

  const concepts = conceptsQuery.data ?? [];
  const current = concepts.find((item) => item.is_current) ?? concepts[0];
  const brief = briefQuery.data;

  return (
    <section className="space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-medium">Concept</h2>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={generate.isPending}
            onClick={() => {
              setError(null);
              generate.mutate();
            }}
            className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
          >
            {generate.isPending ? "Generazione…" : current ? "Rigenera concept homepage" : "Genera concept homepage"}
          </button>
        </div>
      </div>

      {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}

      {brief ? (
        <div className="rounded-xl border border-stone-200 p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium">Design Brief ({brief.source === "manual" ? "modificato a mano" : "automatico"})</h3>
            <div className="flex gap-3 text-sm">
              <button type="button" onClick={() => setEditing((value) => !value)} className="text-stone-600 underline">
                {editing ? "Chiudi" : "Modifica"}
              </button>
              <button type="button" onClick={() => resetBrief.mutate()} className="text-stone-600 underline">
                Rigenera default
              </button>
            </div>
          </div>
          {!editing ? (
            <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-stone-600">
              <span>{brief.style}</span>
              <span className="flex gap-1">
                {(brief.palette ?? []).map((color) => (
                  <span
                    key={color.role}
                    title={`${color.role}: ${color.hex}`}
                    className="h-5 w-5 rounded-full border border-stone-300"
                    style={{ backgroundColor: color.hex }}
                  />
                ))}
              </span>
              <span>{brief.primary_cta}</span>
            </div>
          ) : (
            <DesignBriefForm brief={brief} pending={saveBrief.isPending} onSave={(payload) => saveBrief.mutate(payload)} />
          )}
        </div>
      ) : null}

      <div className="space-y-2">
        {concepts.length === 0 ? (
          <p className="text-sm text-stone-500">
            Nessun concept generato. Richiede un "Approfondisci prospect" avviato almeno una volta.
          </p>
        ) : (
          <ul className="space-y-2">
            {concepts.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-stone-200 px-3 py-2 text-sm"
              >
                <div>
                  <p className="font-medium">
                    V{item.version} {item.is_current ? "· corrente" : ""} · {item.status} ·{" "}
                    {SOURCE_LABELS[item.source] ?? item.source}
                  </p>
                  <p className="text-xs text-stone-500">{new Date(item.created_at).toLocaleString()}</p>
                  {item.error_message ? (
                    <p className="mt-1 text-xs text-amber-700">{item.error_message}</p>
                  ) : null}
                </div>
                <div className="flex gap-3">
                  <a
                    href={conceptFileUrl(item.open_url)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs font-medium hover:bg-stone-50"
                  >
                    Apri concept HTML
                  </a>
                  <button
                    type="button"
                    onClick={() => remove.mutate(item.id)}
                    className="text-xs text-stone-500 underline"
                  >
                    Elimina
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function DesignBriefForm({
  brief,
  onSave,
  pending,
}: {
  brief: DesignBrief;
  onSave: (payload: DesignBriefInput) => void;
  pending: boolean;
}) {
  const [style, setStyle] = useState(brief.style ?? "");
  const [toneOfVoice, setToneOfVoice] = useState(brief.tone_of_voice ?? "");
  const [primaryCta, setPrimaryCta] = useState(brief.primary_cta ?? "");
  const [notes, setNotes] = useState(brief.notes ?? "");
  const [palette, setPalette] = useState(brief.palette ?? []);

  useEffect(() => {
    setStyle(brief.style ?? "");
    setToneOfVoice(brief.tone_of_voice ?? "");
    setPrimaryCta(brief.primary_cta ?? "");
    setNotes(brief.notes ?? "");
    setPalette(brief.palette ?? []);
  }, [brief]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    onSave({ style, tone_of_voice: toneOfVoice, primary_cta: primaryCta, notes, palette });
  }

  return (
    <form onSubmit={onSubmit} className="mt-3 grid gap-2 sm:grid-cols-2">
      <label className="flex flex-col gap-1 text-xs text-stone-500">
        Stile
        <input value={style} onChange={(event) => setStyle(event.target.value)} className="rounded-lg border border-stone-300 px-3 py-2 text-sm" />
      </label>
      <label className="flex flex-col gap-1 text-xs text-stone-500">
        Tone of voice
        <input
          value={toneOfVoice}
          onChange={(event) => setToneOfVoice(event.target.value)}
          className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-stone-500">
        CTA principale
        <input
          value={primaryCta}
          onChange={(event) => setPrimaryCta(event.target.value)}
          className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </label>
      <div className="flex flex-col gap-1 text-xs text-stone-500">
        Palette
        <div className="flex gap-2">
          {palette.map((color, index) => (
            <input
              key={color.role}
              type="color"
              value={color.hex}
              title={color.role}
              onChange={(event) => {
                const next = [...palette];
                next[index] = { ...color, hex: event.target.value };
                setPalette(next);
              }}
              className="h-9 w-9 rounded-lg border border-stone-300"
            />
          ))}
        </div>
      </div>
      <label className="flex flex-col gap-1 text-xs text-stone-500 sm:col-span-2">
        Note
        <textarea
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          rows={2}
          className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </label>
      <button
        type="submit"
        disabled={pending}
        className="w-fit rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 sm:col-span-2"
      >
        {pending ? "Salvataggio…" : "Salva design brief"}
      </button>
    </form>
  );
}
