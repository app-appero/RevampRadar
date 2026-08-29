import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { createAudit } from "../api/audits";
import { fetchCompany } from "../api/discovery";
import { ApiError } from "../api/health";
import { AppShell } from "../components/AppShell";

export function CompanyPage() {
  const { companyId } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["company", companyId],
    queryFn: () => fetchCompany(companyId!),
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

  return (
    <AppShell>
      <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-10">
        <Link to="/companies" className="text-sm text-stone-500 hover:text-stone-900">
          ← Aziende
        </Link>

        {query.isError ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            {query.error instanceof Error ? query.error.message : "Impossibile caricare l'azienda."}
          </p>
        ) : null}

        {company ? (
          <>
            <header className="space-y-2">
              <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">
                {company.status}
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

            {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}

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
            {!company.website_url ? (
              <p className="text-sm text-stone-500">Nessun sito collegato: non è possibile avviare l’audit.</p>
            ) : null}
          </>
        ) : null}
      </main>
    </AppShell>
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
