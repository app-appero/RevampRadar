import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../api/health";
import { fetchCompany, updateCompanyContacts, type SocialLink } from "../api/discovery";

export function CompanyContacts({ companyId }: { companyId: string }) {
  const queryClient = useQueryClient();
  const queryKey = ["company", companyId];
  const companyQuery = useQuery({
    queryKey,
    queryFn: () => fetchCompany(companyId),
  });
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [socials, setSocials] = useState<SocialLink[]>([]);
  const [instagram, setInstagram] = useState("");
  const [lastPost, setLastPost] = useState("");

  useEffect(() => {
    if (!companyQuery.data) return;
    setPhone(companyQuery.data.phone ?? "");
    setEmail(companyQuery.data.email ?? "");
    setSocials(companyQuery.data.social_links ?? []);
    setInstagram(companyQuery.data.instagram_handle ?? "");
    setLastPost(companyQuery.data.instagram_last_post_at ?? "");
  }, [companyQuery.data]);

  const save = useMutation({
    mutationFn: () =>
      updateCompanyContacts(companyId, {
        phone,
        email,
        social_links: socials,
        instagram_handle: instagram.trim() || null,
        instagram_last_post_at: lastPost || null,
      }),
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
        <label className="block space-y-1">
          <span className="text-sm font-medium text-stone-700">Instagram</span>
          <input
            value={instagram}
            onChange={(event) => setInstagram(event.target.value)}
            maxLength={255}
            placeholder="@nomeprofilo"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-sm font-medium text-stone-700">Ultimo post Instagram</span>
          <input
            type="date"
            value={lastPost}
            onChange={(event) => setLastPost(event.target.value)}
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
        </label>
        <div className="space-y-2 sm:col-span-2">
          <span className="text-sm font-medium text-stone-700">Social</span>
          {socials.map((item, index) => (
            <div key={index} className="flex gap-2">
              <input
                value={item.label}
                onChange={(event) =>
                  setSocials(socials.map((row, i) => (i === index ? { ...row, label: event.target.value } : row)))
                }
                maxLength={40}
                placeholder="Facebook, Instagram…"
                aria-label="Nome social"
                className="w-36 rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
              />
              <input
                value={item.url}
                onChange={(event) =>
                  setSocials(socials.map((row, i) => (i === index ? { ...row, url: event.target.value } : row)))
                }
                maxLength={2048}
                placeholder="https://…"
                aria-label="Link social"
                className="min-w-0 flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
              />
              <button
                type="button"
                onClick={() => setSocials(socials.filter((_, i) => i !== index))}
                className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50"
                aria-label="Rimuovi social"
              >
                Rimuovi
              </button>
            </div>
          ))}
          {socials.length < 12 ? (
            <button
              type="button"
              onClick={() => setSocials([...socials, { label: "", url: "" }])}
              className="rounded-lg border border-stone-300 px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-50"
            >
              Aggiungi social
            </button>
          ) : null}
        </div>
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
