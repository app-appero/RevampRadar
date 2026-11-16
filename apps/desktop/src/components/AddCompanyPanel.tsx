import { useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/health";
import { CRM_STATUSES, CRM_STATUS_LABELS, createManualCompany } from "../api/crm";
import {
  MANUAL_COMPANY_METHOD,
  MANUAL_COMPANY_PATH,
  buildManualCompanyBody,
  emptyManualCompanyForm,
  type ManualCompanyForm,
} from "./addCompanyForm";

export function AddCompanyPanel() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ManualCompanyForm>(emptyManualCompanyForm);
  const [error, setError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<{ company_id: string; name: string; city: string | null; reasons: string[] }[]>([]);

  const save = useMutation({
    mutationFn: async (current: ManualCompanyForm) => {
      const body = buildManualCompanyBody(current);
      return createManualCompany(MANUAL_COMPANY_PATH, MANUAL_COMPANY_METHOD, body);
    },
    onSuccess: async (result) => {
      if (result.outcome === "conflict") {
        setError(result.error || "Corrispondenza ambigua: nessuna azienda creata.");
        setCandidates(result.candidates);
        return;
      }
      if (!result.company_id) {
        setError("Il backend non ha restituito l'azienda.");
        return;
      }
      await queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      await queryClient.invalidateQueries({ queryKey: ["crm-dashboard"] });
      await queryClient.invalidateQueries({ queryKey: ["companies"] });
      await queryClient.invalidateQueries({ queryKey: ["company", result.company_id] });
      await queryClient.invalidateQueries({ queryKey: ["company-opportunity", result.company_id] });
      navigate(`/companies/${result.company_id}`);
    },
    onError: (err) => {
      setCandidates([]);
      setError(err instanceof ApiError ? err.message : "Salvataggio non riuscito.");
    },
  });

  const set = (patch: Partial<ManualCompanyForm>) => setForm((current) => ({ ...current, ...patch }));

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-stone-900">Anagrafica</h2>
          <p className="text-sm text-stone-600">
            Aggiungi un'azienda al CRM senza analizzarla. L'analisi resta un'azione a parte.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setOpen((value) => !value);
            setError(null);
          }}
          aria-expanded={open}
          className="rounded-lg border border-stone-300 px-3 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50"
        >
          Aggiungi azienda
        </button>
      </div>
      {open ? (
        <form
          className="mt-4 grid gap-3 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            setError(null);
            setCandidates([]);
            save.mutate(form);
          }}
        >
          <Field label="Nome" required>
            <input
              required
              value={form.name}
              onChange={(event) => set({ name: event.target.value })}
              className={inputClass}
            />
          </Field>
          <Field label="Sito">
            <input
              value={form.websiteUrl}
              onChange={(event) => set({ websiteUrl: event.target.value })}
              placeholder="Facoltativo"
              className={inputClass}
            />
          </Field>
          <Field label="Email">
            <input
              value={form.email}
              onChange={(event) => set({ email: event.target.value })}
              className={inputClass}
            />
          </Field>
          <Field label="Telefono">
            <input
              value={form.phone}
              onChange={(event) => set({ phone: event.target.value })}
              className={inputClass}
            />
          </Field>
          <Field label="Settore">
            <input value={form.category} onChange={(event) => set({ category: event.target.value })} className={inputClass} />
          </Field>
          <Field label="Città">
            <input value={form.city} onChange={(event) => set({ city: event.target.value })} className={inputClass} />
          </Field>
          <Field label="Provincia">
            <input value={form.province} onChange={(event) => set({ province: event.target.value })} className={inputClass} />
          </Field>
          <Field label="Regione">
            <input value={form.region} onChange={(event) => set({ region: event.target.value })} className={inputClass} />
          </Field>
          <Field label="Fonte">
            <input
              value={form.source}
              onChange={(event) => set({ source: event.target.value })}
              placeholder="manual se vuota"
              className={inputClass}
            />
          </Field>
          <Field label="Stato CRM">
            <select value={form.status} onChange={(event) => set({ status: event.target.value })} className={inputClass}>
              {CRM_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {CRM_STATUS_LABELS[status] ?? status}
                </option>
              ))}
            </select>
          </Field>
          <div className="sm:col-span-2 grid gap-2">
            <span className="text-xs font-medium tracking-wide text-stone-500 uppercase">Social</span>
            {form.socialLinks.map((link, index) => (
              <div key={index} className="grid gap-2 sm:grid-cols-2">
                <input
                  value={link.label}
                  onChange={(event) => {
                    const socialLinks = form.socialLinks.slice();
                    socialLinks[index] = { ...link, label: event.target.value };
                    set({ socialLinks });
                  }}
                  placeholder="Instagram"
                  aria-label={`Social ${index + 1}`}
                  className={inputClass}
                />
                <input
                  value={link.url}
                  onChange={(event) => {
                    const socialLinks = form.socialLinks.slice();
                    socialLinks[index] = { ...link, url: event.target.value };
                    set({ socialLinks });
                  }}
                  placeholder="URL o @handle"
                  aria-label={`URL social ${index + 1}`}
                  className={inputClass}
                />
              </div>
            ))}
          </div>
          <Field label="Note">
            <textarea
              value={form.notes}
              onChange={(event) => set({ notes: event.target.value })}
              rows={3}
              className={inputClass}
            />
          </Field>
          <Field label="Tag">
            <input
              value={form.tags}
              onChange={(event) => set({ tags: event.target.value })}
              placeholder="Separati da virgola"
              className={inputClass}
            />
          </Field>
          {error ? (
            <p role="alert" className="sm:col-span-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
              {error}
            </p>
          ) : null}
          {candidates.length ? (
            <ul className="sm:col-span-2 space-y-1 text-sm text-stone-700">
              {candidates.map((item) => (
                <li key={item.company_id}>
                  <a className="underline" href={`/companies/${item.company_id}`}>
                    {item.name}
                    {item.city ? ` · ${item.city}` : ""}
                  </a>
                  <span className="text-stone-500"> — {item.reasons.join(", ")}</span>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={save.isPending}
              className="rounded-lg border border-stone-900 px-3 py-2 text-sm font-medium text-stone-900 hover:bg-stone-50 disabled:opacity-50"
            >
              {save.isPending ? "Salvataggio…" : "Salva azienda"}
            </button>
            <p className="text-xs text-stone-500">
              Salva solo l'anagrafica. Non avvia audit, scanner o ricerche. Per analizzare un sito usa «Analizza sito».
            </p>
          </div>
        </form>
      ) : null}
    </section>
  );
}

const inputClass = "w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900";

function Field({ label, required, children }: { label: string; required?: boolean; children: ReactNode }) {
  return (
    <label className="grid gap-1 text-sm text-stone-700">
      <span className="text-xs font-medium tracking-wide text-stone-500 uppercase">
        {label}
        {required ? " *" : ""}
      </span>
      {children}
    </label>
  );
}
