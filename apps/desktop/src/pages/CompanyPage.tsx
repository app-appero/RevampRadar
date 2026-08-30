import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { createAudit } from "../api/audits";
import {
  ACTIVITY_LABELS,
  ACTIVITY_TYPES,
  CRM_STATUSES,
  CRM_STATUS_LABELS,
  addActivity,
  addNote,
  addTag,
  fetchCompanyOpportunity,
  removeTag,
  updateOpportunity,
  type OpportunityDetail,
} from "../api/crm";
import { fetchCompany } from "../api/discovery";
import { ApiError } from "../api/health";
import { AppShell } from "../components/AppShell";

export function CompanyPage() {
  const { companyId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["company", companyId],
    queryFn: () => fetchCompany(companyId!),
    enabled: Boolean(companyId),
  });
  const crmQuery = useQuery({
    queryKey: ["company-opportunity", companyId],
    queryFn: () => fetchCompanyOpportunity(companyId!),
    enabled: Boolean(companyId),
  });
  const analyze = useMutation({
    mutationFn: async () => {
      const company = query.data;
      if (!company?.website_url) {
        throw new ApiError("Questa azienda non ha un sito da analizzare.");
      }
      return createAudit(company.website_url, company.id);
    },
    onSuccess: (audit) => navigate(`/audits/${audit.id}`),
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Analisi non avviata.");
    },
  });
  const company = query.data;
  const opportunity = crmQuery.data;

  function invalidateCrm() {
    void queryClient.invalidateQueries({ queryKey: ["company-opportunity", companyId] });
    void queryClient.invalidateQueries({ queryKey: ["opportunities"] });
    void queryClient.invalidateQueries({ queryKey: ["crm-dashboard"] });
  }

  return (
    <AppShell>
      <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-10">
        <Link to="/pipeline" className="text-sm text-stone-500 hover:text-stone-900">
          ← Pipeline
        </Link>

        {query.isError || crmQuery.isError ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            Impossibile caricare l'azienda.
          </p>
        ) : null}

        {company ? (
          <>
            <header className="space-y-2">
              <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">
                {opportunity
                  ? `${opportunity.is_favorite ? "★ " : ""}${CRM_STATUS_LABELS[opportunity.status] ?? opportunity.status}`
                  : company.status}
              </p>
              <h1 className="text-3xl font-semibold tracking-tight">{company.name}</h1>
              <p className="text-stone-600">
                {[company.city, company.region, company.country].filter(Boolean).join(" · ") || "Località non indicata"}
              </p>
            </header>

            <section className="grid gap-4 sm:grid-cols-2">
              <Field label="Categoria" value={company.category} />
              <Field label="Telefono" value={company.phone} />
              <Field label="Email" value={company.email} />
              <Field label="Fonte" value={`${company.source}${company.external_id ? ` · ${company.external_id}` : ""}`} />
              <Field label="Sito" value={company.website_url} />
              <Field label="Dominio" value={company.domain} />
            </section>

            {opportunity ? (
              <section className="grid gap-4 sm:grid-cols-3">
                <Field label="Website Score" value={opportunity.website_score?.toString()} />
                <Field label="Opportunity Score" value={opportunity.opportunity_score?.toString()} />
                <Field
                  label="Priorità"
                  value={
                    opportunity.latest_audit_id
                      ? opportunity.priority
                      : opportunity.priority
                  }
                />
              </section>
            ) : null}

            {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                disabled={!company.website_url || analyze.isPending}
                onClick={() => {
                  setError(null);
                  analyze.mutate();
                }}
                className="w-fit rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
              >
                {analyze.isPending ? "Avvio…" : "Analizza sito"}
              </button>
              {opportunity?.latest_audit_id ? (
                <Link
                  to={`/audits/${opportunity.latest_audit_id}`}
                  className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50"
                >
                  Apri ultimo audit
                </Link>
              ) : null}
            </div>
            {!company.website_url ? (
              <p className="text-sm text-stone-500">Nessun sito collegato: non è possibile avviare l’audit.</p>
            ) : null}

            {opportunity ? <CrmPanel opportunity={opportunity} onChanged={invalidateCrm} /> : null}
          </>
        ) : null}
      </main>
    </AppShell>
  );
}

function CrmPanel({
  opportunity,
  onChanged,
}: {
  opportunity: OpportunityDetail;
  onChanged: () => void;
}) {
  const [note, setNote] = useState("");
  const [tag, setTag] = useState("");
  const [activityType, setActivityType] = useState("call");
  const [activityNote, setActivityNote] = useState("");
  const [crmError, setCrmError] = useState<string | null>(null);

  const mutate = useMutation({
    mutationFn: async (action: () => Promise<OpportunityDetail>) => action(),
    onSuccess: () => {
      setCrmError(null);
      onChanged();
    },
    onError: (err) => {
      setCrmError(err instanceof ApiError ? err.message : "Operazione CRM non riuscita.");
    },
  });

  function onAddNote(event: FormEvent) {
    event.preventDefault();
    if (!note.trim()) return;
    mutate.mutate(async () => {
      const result = await addNote(opportunity.id, note);
      setNote("");
      return result;
    });
  }

  function onAddTag(event: FormEvent) {
    event.preventDefault();
    if (!tag.trim()) return;
    mutate.mutate(async () => {
      const result = await addTag(opportunity.id, tag);
      setTag("");
      return result;
    });
  }

  function onAddActivity(event: FormEvent) {
    event.preventDefault();
    mutate.mutate(async () => {
      const result = await addActivity(opportunity.id, {
        type: activityType,
        note: activityNote.trim() || undefined,
      });
      setActivityNote("");
      return result;
    });
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs tracking-wide text-stone-500 uppercase">Stato CRM</span>
          <select
            value={opportunity.status}
            disabled={mutate.isPending}
            onChange={(event) =>
              mutate.mutate(() => updateOpportunity(opportunity.id, { status: event.target.value }))
            }
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          >
            {CRM_STATUSES.map((status) => (
              <option key={status} value={status}>
                {CRM_STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={mutate.isPending}
          onClick={() =>
            mutate.mutate(() => updateOpportunity(opportunity.id, { is_favorite: !opportunity.is_favorite }))
          }
          className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50"
        >
          {opportunity.is_favorite ? "Togli dai preferiti" : "Aggiungi ai preferiti"}
        </button>
      </div>

      {crmError ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{crmError}</p> : null}

      <div className="space-y-2">
        <h2 className="text-lg font-medium">Tag</h2>
        <div className="flex flex-wrap gap-2">
          {opportunity.tags.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => mutate.mutate(() => removeTag(opportunity.id, item.id))}
              className="rounded-full bg-stone-100 px-3 py-1 text-xs text-stone-700 hover:bg-stone-200"
            >
              {item.name} ×
            </button>
          ))}
        </div>
        <form onSubmit={onAddTag} className="flex gap-2">
          <input
            value={tag}
            onChange={(event) => setTag(event.target.value)}
            placeholder="Nuovo tag"
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
          <button type="submit" className="rounded-lg border border-stone-300 px-3 py-2 text-sm">
            Aggiungi
          </button>
        </form>
      </div>

      <div className="space-y-2">
        <h2 className="text-lg font-medium">Note</h2>
        <form onSubmit={onAddNote} className="flex flex-col gap-2">
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Annotazione commerciale"
            rows={3}
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
          <button type="submit" className="w-fit rounded-lg bg-stone-900 px-3 py-2 text-sm text-white">
            Salva nota
          </button>
        </form>
        <ul className="space-y-2">
          {opportunity.notes.map((item) => (
            <li key={item.id} className="rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm">
              <p>{item.body}</p>
              <p className="mt-1 text-xs text-stone-500">{new Date(item.created_at).toLocaleString()}</p>
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-2">
        <h2 className="text-lg font-medium">Attività</h2>
        <form onSubmit={onAddActivity} className="flex flex-col gap-2 sm:flex-row">
          <select
            value={activityType}
            onChange={(event) => setActivityType(event.target.value)}
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          >
            {ACTIVITY_TYPES.map((item) => (
              <option key={item} value={item}>
                {ACTIVITY_LABELS[item]}
              </option>
            ))}
          </select>
          <input
            value={activityNote}
            onChange={(event) => setActivityNote(event.target.value)}
            placeholder="Dettaglio attività"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
          <button type="submit" className="rounded-lg border border-stone-300 px-3 py-2 text-sm whitespace-nowrap">
            Registra
          </button>
        </form>
        <ul className="space-y-2">
          {opportunity.activities.map((item) => (
            <li key={item.id} className="rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm">
              <p className="font-medium">{ACTIVITY_LABELS[item.type] ?? item.type}</p>
              {item.note ? <p className="text-stone-700">{item.note}</p> : null}
              <p className="mt-1 text-xs text-stone-500">{new Date(item.occurred_at).toLocaleString()}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
      <p className="text-xs tracking-wide text-stone-500 uppercase">{label}</p>
      <p className="mt-1 text-sm font-medium break-all">{value || "—"}</p>
    </div>
  );
}
