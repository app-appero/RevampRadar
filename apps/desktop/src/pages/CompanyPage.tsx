import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { createAudit } from "../api/audits";
import {
  ACTIVITY_LABELS,
  ACTIVITY_TYPES,
  SCHEDULED_ACTIVITY_TYPES,
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
import { fetchCompanyIntelligence } from "../api/intelligence";
import { fetchCompanyGrowthScore } from "../api/growth";
import { generateGreenfieldProposal, generateProposal, fetchCompanyProposal } from "../api/proposals";
import { IntelligencePanel } from "../components/IntelligencePanel";
import { fetchCompany, formatOsmTags } from "../api/discovery";
import { ProposalCard } from "../components/ProposalCard";
import { ApiError } from "../api/health";
import { PageBackLink } from "../components/HistoryNav";
import { ExternalLink } from "../components/ExternalLink";

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
  const intelligenceQuery = useQuery({
    queryKey: ["company-intelligence", companyId],
    queryFn: () => fetchCompanyIntelligence(companyId!),
    enabled: Boolean(companyId),
    retry: false,
  });
  const proposalQuery = useQuery({
    queryKey: ["company-proposal", companyId],
    queryFn: () => fetchCompanyProposal(companyId!),
    enabled: Boolean(companyId),
    retry: false,
  });
  const growthQuery = useQuery({
    queryKey: ["company-growth", companyId],
    queryFn: () => fetchCompanyGrowthScore(companyId!),
    enabled: Boolean(companyId) && query.isSuccess && !query.data?.website_url,
    retry: false,
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
  const generateProposalMut = useMutation({
    mutationFn: async () => {
      const auditId = crmQuery.data?.latest_audit_id;
      if (!auditId) {
        throw new ApiError("Serve un audit completato per generare la proposta.");
      }
      return generateProposal(auditId);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["company-proposal", companyId] });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Proposta non generata.");
    },
  });
  const generateGreenfieldMut = useMutation({
    mutationFn: async () => generateGreenfieldProposal(companyId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["company-proposal", companyId] });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Proposta non generata.");
    },
  });
  const company = query.data;
  const opportunity = crmQuery.data;

  function invalidateCrm(data?: OpportunityDetail) {
    if (data) {
      queryClient.setQueryData(["company-opportunity", companyId], data);
    }
    void queryClient.invalidateQueries({ queryKey: ["company-opportunity", companyId] });
    void queryClient.invalidateQueries({ queryKey: ["opportunities"] });
    void queryClient.invalidateQueries({ queryKey: ["crm-dashboard"] });
  }

  return (
      <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-10">
        <PageBackLink fallback="/pipeline" label="Indietro" />

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
              <Field label="Tag OSM" value={formatOsmTags(company.osm_tags) || null} />
              <Field label="Apertura (OSM)" value={company.osm_start_date} />
              <Field label="Orari (OSM)" value={company.osm_opening_hours} />
              <Field label="Telefono" value={company.phone} />
              <Field label="Email" value={company.email} />
              <SocialLinksField links={company.social_links} />
              <Field label="Fonte" value={`${company.source}${company.external_id ? ` · ${company.external_id}` : ""}`} />
              <Field label="Sito" value={company.website_url} href={company.website_url} />
              <Field label="Dominio" value={company.domain} />
            </section>
            {!company.phone && !company.email && (company.social_links?.length ?? 0) > 0 ? (
              <p className="text-sm text-stone-500">
                Nessun telefono/email su OSM: come contatto alternativo{" "}
                {(company.social_links ?? []).length > 1 ? "ci sono queste pagine" : "c'è questa pagina"}.
              </p>
            ) : null}

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
              <ExternalLink
                href={googleMapsSearchUrl(company.name, company.city, company.latitude, company.longitude)}
                className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50"
              >
                Cerca su Google Maps
              </ExternalLink>
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
              {opportunity?.latest_audit_id ? (
                <button
                  type="button"
                  disabled={generateProposalMut.isPending}
                  onClick={() => {
                    setError(null);
                    generateProposalMut.mutate();
                  }}
                  className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50 disabled:opacity-50"
                >
                  {generateProposalMut.isPending ? "Generazione…" : "Genera proposta"}
                </button>
              ) : null}
              {!company.website_url ? (
                <button
                  type="button"
                  disabled={generateGreenfieldMut.isPending}
                  onClick={() => {
                    setError(null);
                    generateGreenfieldMut.mutate();
                  }}
                  className="rounded-lg bg-amber-700 px-4 py-2 text-sm font-medium text-white hover:bg-amber-800 disabled:opacity-50"
                >
                  {generateGreenfieldMut.isPending ? "Generazione…" : "Genera proposta di creazione sito"}
                </button>
              ) : null}
            </div>
            {!company.website_url ? (
              <p className="text-sm text-stone-500">
                Nessun sito collegato: non è possibile avviare l'audit. Questa azienda rientra nel segmento
                "da creare".
              </p>
            ) : null}

            {!company.website_url && growthQuery.data ? (
              <section className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50 p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-medium">Growth Potential Score</h2>
                  <p className="text-2xl font-semibold">
                    {growthQuery.data.score}/100{" "}
                    <span className="text-sm font-normal text-stone-600">({growthQuery.data.priority})</span>
                  </p>
                </div>
                <p className="text-sm text-stone-700">{growthQuery.data.explanation}</p>
                <p className="text-sm font-medium">Servizio indicato: {growthQuery.data.recommended_service}</p>
                {growthQuery.data.top_reasons.length > 0 ? (
                  <div>
                    <h3 className="text-xs tracking-wide text-stone-500 uppercase">Motivi principali</h3>
                    <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-stone-700">
                      {growthQuery.data.top_reasons.map((reason, index) => (
                        <li key={index}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <p className="text-xs text-stone-500">
                  Stima euristica basata su categoria, concorrenza locale con sito e contattabilità (campione:{" "}
                  {growthQuery.data.peer_sample_size} attività simili) — non è un'analisi di un sito esistente.
                </p>
              </section>
            ) : null}

            {intelligenceQuery.data ? <IntelligencePanel data={intelligenceQuery.data} /> : null}

            {proposalQuery.data ? (
              <section className="space-y-3">
                <h2 className="text-lg font-medium">Proposta commerciale</h2>
                <ProposalCard proposal={proposalQuery.data} />
              </section>
            ) : null}

            {opportunity ? <CrmPanel opportunity={opportunity} onChanged={invalidateCrm} /> : null}
          </>
        ) : null}
      </main>
  );
}

function CrmPanel({
  opportunity,
  onChanged,
}: {
  opportunity: OpportunityDetail;
  onChanged: (data?: OpportunityDetail) => void;
}) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [tag, setTag] = useState("");
  const [activityType, setActivityType] = useState("call");
  const [activityNote, setActivityNote] = useState("");
  const [activityMode, setActivityMode] = useState<"log" | "schedule">("log");
  const [dueAt, setDueAt] = useState(() => defaultDueAtLocal());
  const [crmError, setCrmError] = useState<string | null>(null);
  const [status, setStatus] = useState(opportunity.status);

  useEffect(() => {
    setStatus(opportunity.status);
  }, [opportunity.status]);

  const mutate = useMutation({
    mutationFn: async (action: () => Promise<OpportunityDetail>) => action(),
    onSuccess: (data) => {
      setCrmError(null);
      onChanged(data);
    },
    onError: (err) => {
      setStatus(opportunity.status);
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
      if (activityMode === "schedule") {
        const result = await addActivity(opportunity.id, {
          type: activityType,
          note: activityNote.trim() || undefined,
          due_at: new Date(dueAt).toISOString(),
        });
        setActivityNote("");
        void queryClient.invalidateQueries({ queryKey: ["agenda"] });
        return result;
      }
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
            value={status}
            disabled={mutate.isPending}
            onChange={(event) => {
              const next = event.target.value;
              setStatus(next);
              mutate.mutate(() => updateOpportunity(opportunity.id, { status: next }));
            }}
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
        <div className="flex gap-2 text-sm">
          <button
            type="button"
            onClick={() => setActivityMode("log")}
            className={`rounded-lg px-3 py-1.5 ${
              activityMode === "log"
                ? "bg-stone-900 text-white"
                : "border border-stone-300 text-stone-700"
            }`}
          >
            Registra
          </button>
          <button
            type="button"
            onClick={() => {
              setActivityMode("schedule");
              if (!SCHEDULED_ACTIVITY_TYPES.includes(activityType as (typeof SCHEDULED_ACTIVITY_TYPES)[number])) {
                setActivityType("call");
              }
            }}
            className={`rounded-lg px-3 py-1.5 ${
              activityMode === "schedule"
                ? "bg-stone-900 text-white"
                : "border border-stone-300 text-stone-700"
            }`}
          >
            Pianifica
          </button>
        </div>
        <form onSubmit={onAddActivity} className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <select
            value={activityType}
            onChange={(event) => setActivityType(event.target.value)}
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          >
            {(activityMode === "schedule" ? SCHEDULED_ACTIVITY_TYPES : ACTIVITY_TYPES).map((item) => (
              <option key={item} value={item}>
                {ACTIVITY_LABELS[item]}
              </option>
            ))}
          </select>
          {activityMode === "schedule" ? (
            <input
              type="datetime-local"
              value={dueAt}
              onChange={(event) => setDueAt(event.target.value)}
              className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
            />
          ) : null}
          <input
            value={activityNote}
            onChange={(event) => setActivityNote(event.target.value)}
            placeholder={activityMode === "schedule" ? "Promemoria" : "Dettaglio attività"}
            className="w-full min-w-[12rem] flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
          <button type="submit" className="rounded-lg border border-stone-300 px-3 py-2 text-sm whitespace-nowrap">
            {activityMode === "schedule" ? "Pianifica" : "Registra"}
          </button>
        </form>
        <ul className="space-y-2">
          {opportunity.activities.map((item) => {
            const pending = item.due_at && !item.completed_at;
            const when = pending
              ? item.due_at
              : item.occurred_at ?? item.completed_at ?? item.created_at;
            return (
              <li
                key={item.id}
                className={`rounded-xl border px-3 py-2 text-sm ${
                  pending ? "border-amber-200 bg-amber-50" : "border-stone-200 bg-white"
                }`}
              >
                <p className="font-medium">
                  {ACTIVITY_LABELS[item.type] ?? item.type}
                  {pending ? (
                    <span className="ml-2 text-xs font-normal text-amber-800">Pianificata</span>
                  ) : null}
                </p>
                {item.note ? <p className="text-stone-700">{item.note}</p> : null}
                {when ? (
                  <p className="mt-1 text-xs text-stone-500">{new Date(when).toLocaleString()}</p>
                ) : null}
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

function googleMapsSearchUrl(
  name: string,
  city: string | null,
  latitude?: number | null,
  longitude?: number | null,
): string {
  if (latitude != null && longitude != null) {
    return `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;
  }
  const query = [name, city].filter(Boolean).join(" ");
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

function defaultDueAtLocal(): string {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(10, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function Field({
  label,
  value,
  href,
}: {
  label: string;
  value: string | null | undefined;
  href?: string | null;
}) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
      <p className="text-xs tracking-wide text-stone-500 uppercase">{label}</p>
      {href && value ? (
        <ExternalLink href={href} className="mt-1 block text-sm font-medium break-all underline">
          {value}
        </ExternalLink>
      ) : (
        <p className="mt-1 text-sm font-medium break-all">{value || "—"}</p>
      )}
    </div>
  );
}

function SocialLinksField({ links }: { links?: { label: string; url: string }[] }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
      <p className="text-xs tracking-wide text-stone-500 uppercase">Contatto social</p>
      {links && links.length > 0 ? (
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
          {links.map((item) => (
            <ExternalLink key={item.url} href={item.url} className="text-sm font-medium underline">
              {item.label}
            </ExternalLink>
          ))}
        </div>
      ) : (
        <p className="mt-1 text-sm font-medium">—</p>
      )}
    </div>
  );
}
