import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../api/health";
import { fetchCompany, updateCompanyContacts } from "../api/discovery";

export function CompanyContacts({ companyId }: { companyId: string }) {
  const queryClient = useQueryClient();
  const queryKey = ["company", companyId];
  const companyQuery = useQuery({
    queryKey,
    queryFn: () => fetchCompany(companyId),
  });
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");

  useEffect(() => {
    if (!companyQuery.data) return;
    setPhone(companyQuery.data.phone ?? "");
    setEmail(companyQuery.data.email ?? "");
  }, [companyQuery.data]);

  const save = useMutation({
    mutationFn: () => updateCompanyContacts(companyId, { phone, email }),
    onSuccess: (company) => {
      queryClient.setQueryData(queryKey, company);
      void queryClient.invalidateQueries({ queryKey: ["companies"] });
      void queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      void queryClient.invalidateQueries({ queryKey: ["crm-dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["company-opportunity", companyId] });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  const company = companyQuery.data;
  if (companyQuery.isLoading) return <p className="text-sm text-stone-500">Caricamento contatti…</p>;
  if (companyQuery.isError || !company) {
    return <p className="text-sm text-red-700">Impossibile caricare i contatti dell’azienda.</p>;
  }

  const verification = company.places_checked_at
    ? company.email
      ? "Visto"
      : company.phone
        ? "Visto - senza email"
        : "Visto - senza contatti"
    : "Non visto";

  return (
    <section className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-medium">Contatti</h2>
        <span className="rounded-full bg-stone-100 px-2.5 py-1 text-xs font-medium text-stone-700">
          {verification}
        </span>
      </div>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <label className="block space-y-1">
          <span className="text-sm font-medium text-stone-700">Telefono</span>
          <input
            type="tel"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            maxLength={64}
            placeholder="Numero trovato sui social o sul sito"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-sm font-medium text-stone-700">Email</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            maxLength={255}
            placeholder="Indirizzo email pubblico"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
        </label>
        <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
          <button
            type="submit"
            disabled={save.isPending}
            className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
          >
            {save.isPending ? "Salvataggio…" : "Salva contatti"}
          </button>
          {save.isSuccess ? <span className="text-sm text-emerald-800">Contatti salvati.</span> : null}
          {save.isError ? (
            <span className="text-sm text-red-700">
              {save.error instanceof ApiError ? save.error.message : "Salvataggio non riuscito."}
            </span>
          ) : null}
        </div>
      </form>
      <p className="text-xs text-stone-500">
        Dopo aver salvato almeno un contatto, l’azienda risulta verificata e lo stato si aggiorna in base a email e telefono.
      </p>
    </section>
  );
}
