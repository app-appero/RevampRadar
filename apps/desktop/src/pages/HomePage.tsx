import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createAudit } from "../api/audits";
import { ApiError } from "../api/health";
import { AppShell } from "../components/AppShell";

export function HomePage() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const audit = await createAudit(url);
      navigate(`/audits/${audit.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Analisi non avviata.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AppShell>
      <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-12">
        <header className="space-y-2">
          <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">
            Single Website Analyzer
          </p>
          <h1 className="text-4xl font-semibold tracking-tight">Analizza un sito</h1>
          <p className="max-w-xl text-stone-600">
            Inserisci un URL. RevampRadar produce un audit tecnico con finding,
            screenshot e controlli SEO di base.
          </p>
        </header>

        <form
          onSubmit={(event) => void onSubmit(event)}
          className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm"
        >
          <label htmlFor="url" className="text-sm font-medium text-stone-700">
            URL del sito
          </label>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row">
            <input
              id="url"
              name="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="es. hotel-esempio.it"
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
              disabled={submitting}
              autoFocus
            />
            <button
              type="submit"
              disabled={submitting || url.trim().length === 0}
              className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium whitespace-nowrap text-white hover:bg-stone-800 disabled:opacity-50"
            >
              {submitting ? "Avvio…" : "Avvia analisi"}
            </button>
          </div>
          {error ? (
            <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
          ) : null}
        </form>
      </main>
    </AppShell>
  );
}
