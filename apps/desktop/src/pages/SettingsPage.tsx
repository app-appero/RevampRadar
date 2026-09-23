import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ApiError } from "../api/health";
import {
  fetchEmailTemplates,
  fetchSenderProfile,
  saveEmailTemplates,
  saveSenderProfile,
  type ProfileLink,
} from "../api/settings";

export function SettingsPage() {
  const profileQuery = useQuery({
    queryKey: ["sender-profile"],
    queryFn: fetchSenderProfile,
  });
  const [displayName, setDisplayName] = useState("");
  const [intro, setIntro] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [freelancerLinks, setFreelancerLinks] = useState<ProfileLink[]>([]);
  const [socialLinks, setSocialLinks] = useState<ProfileLink[]>([]);

  useEffect(() => {
    const profile = profileQuery.data;
    if (!profile) return;
    setDisplayName(profile.display_name);
    setIntro(profile.intro);
    setWebsiteUrl(profile.website_url);
    setFreelancerLinks(profile.freelancer_links);
    setSocialLinks(profile.social_links);
  }, [profileQuery.data]);

  const save = useMutation({
    mutationFn: () =>
      saveSenderProfile({
        display_name: displayName.trim(),
        intro: intro.trim(),
        website_url: websiteUrl.trim(),
        freelancer_links: freelancerLinks.filter((item) => item.label.trim() && item.url.trim()),
        social_links: socialLinks.filter((item) => item.label.trim() && item.url.trim()),
      }),
    onSuccess: () => {
      void profileQuery.refetch();
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
      <header className="space-y-2">
        <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">Profilo</p>
        <h1 className="text-3xl font-semibold tracking-tight">Impostazioni</h1>
        <p className="max-w-2xl text-stone-600">
          Nome, sito, piattaforme freelance e social finiscono in firma nell’email
          al prospect. Il range di prezzo resta solo visibile a te, nella scheda proposta.
        </p>
      </header>

      {profileQuery.isError ? (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
          {profileQuery.error instanceof ApiError
            ? profileQuery.error.message
            : "Impossibile caricare il profilo."}
        </p>
      ) : null}

      <form onSubmit={onSubmit} className="space-y-6 rounded-2xl border border-stone-200 bg-white p-6">
        <label className="block space-y-1">
          <span className="text-sm font-medium text-stone-700">Il tuo nome</span>
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
            required
          />
        </label>

        <label className="block space-y-1">
          <span className="text-sm font-medium text-stone-700">Chi sei e cosa fai</span>
          <textarea
            value={intro}
            onChange={(event) => setIntro(event.target.value)}
            rows={4}
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
            required
          />
        </label>

        <label className="block space-y-1">
          <span className="text-sm font-medium text-stone-700">Il tuo sito</span>
          <input
            value={websiteUrl}
            onChange={(event) => setWebsiteUrl(event.target.value)}
            placeholder="https://"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
            required
          />
        </label>

        <LinkList
          title="Piattaforme freelance"
          links={freelancerLinks}
          onChange={setFreelancerLinks}
        />
        <LinkList title="Social" links={socialLinks} onChange={setSocialLinks} />

        {save.isError ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            {save.error instanceof ApiError ? save.error.message : "Salvataggio non riuscito."}
          </p>
        ) : null}
        {save.isSuccess ? (
          <p className="text-sm text-emerald-800">Profilo salvato. Rigenera le proposte per aggiornare le email già create.</p>
        ) : null}

        <button
          type="submit"
          disabled={save.isPending || profileQuery.isLoading}
          className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
        >
          {save.isPending ? "Salvataggio…" : "Salva"}
        </button>
      </form>

      <EmailTemplatesEditor />
    </main>
  );
}

function EmailTemplatesEditor() {
  const templatesQuery = useQuery({
    queryKey: ["email-templates"],
    queryFn: fetchEmailTemplates,
  });
  const [refactorBody, setRefactorBody] = useState("");
  const [greenfieldBody, setGreenfieldBody] = useState("");

  useEffect(() => {
    const data = templatesQuery.data;
    if (!data) return;
    setRefactorBody(data.refactor_body ?? data.refactor_default);
    setGreenfieldBody(data.greenfield_body ?? data.greenfield_default);
  }, [templatesQuery.data]);

  const save = useMutation({
    mutationFn: () =>
      saveEmailTemplates({
        refactor_body: refactorBody.trim() || null,
        greenfield_body: greenfieldBody.trim() || null,
      }),
    onSuccess: () => {
      void templatesQuery.refetch();
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  const data = templatesQuery.data;

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">Proposte</p>
        <h2 className="text-xl font-semibold tracking-tight">Template email</h2>
        <p className="max-w-2xl text-stone-600">
          Il testo che finisce nelle email generate per le proposte. Usa i placeholder tra doppie
          parentesi graffe: vengono sostituiti con i dati dell'azienda e i tuoi dati da qui sopra
          quando generi una proposta.
        </p>
      </header>

      {templatesQuery.isError ? (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
          {templatesQuery.error instanceof ApiError
            ? templatesQuery.error.message
            : "Impossibile caricare i template."}
        </p>
      ) : null}

      {data ? (
        <form onSubmit={onSubmit} className="space-y-6 rounded-2xl border border-stone-200 bg-white p-6">
          <TemplateField
            label="Email — azienda con sito (da rifare)"
            value={refactorBody}
            onChange={setRefactorBody}
            tokens={data.refactor_tokens}
            onReset={() => setRefactorBody(data.refactor_default)}
          />
          <TemplateField
            label="Email — azienda senza sito (da creare)"
            value={greenfieldBody}
            onChange={setGreenfieldBody}
            tokens={data.greenfield_tokens}
            onReset={() => setGreenfieldBody(data.greenfield_default)}
          />

          {save.isError ? (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
              {save.error instanceof ApiError ? save.error.message : "Salvataggio non riuscito."}
            </p>
          ) : null}
          {save.isSuccess ? (
            <p className="text-sm text-emerald-800">
              Template salvati. Le proposte già generate non cambiano; rigenerale per usare il nuovo testo.
            </p>
          ) : null}

          <button
            type="submit"
            disabled={save.isPending}
            className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
          >
            {save.isPending ? "Salvataggio…" : "Salva template"}
          </button>
        </form>
      ) : null}
    </section>
  );
}

function TemplateField({
  label,
  value,
  onChange,
  tokens,
  onReset,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  tokens: string[];
  onReset: () => void;
}) {
  return (
    <label className="block space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-stone-700">{label}</span>
        <button type="button" onClick={onReset} className="text-xs text-stone-500 underline">
          Ripristina il default
        </button>
      </div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={12}
        className="w-full rounded-lg border border-stone-300 px-3 py-2 font-mono text-sm outline-none focus:border-stone-900"
      />
      <p className="text-xs text-stone-500">
        Placeholder disponibili: {tokens.map((token) => `{{${token}}}`).join(", ")}
      </p>
    </label>
  );
}

function LinkList({
  title,
  links,
  onChange,
}: {
  title: string;
  links: ProfileLink[];
  onChange: (next: ProfileLink[]) => void;
}) {
  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-medium text-stone-700">{title}</legend>
      {links.map((item, index) => (
        <div key={`${title}-${index}`} className="flex flex-col gap-2 sm:flex-row">
          <input
            value={item.label}
            onChange={(event) => {
              const next = [...links];
              next[index] = { ...item, label: event.target.value };
              onChange(next);
            }}
            placeholder="Nome"
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900 sm:w-40"
          />
          <input
            value={item.url}
            onChange={(event) => {
              const next = [...links];
              next[index] = { ...item, url: event.target.value };
              onChange(next);
            }}
            placeholder="https://"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
          />
          <button
            type="button"
            className="text-sm text-stone-600 underline"
            onClick={() => onChange(links.filter((_, itemIndex) => itemIndex !== index))}
          >
            Rimuovi
          </button>
        </div>
      ))}
      <button
        type="button"
        className="text-sm underline"
        onClick={() => onChange([...links, { label: "", url: "" }])}
      >
        Aggiungi
      </button>
    </fieldset>
  );
}
