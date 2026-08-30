import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createDiscovery } from "../api/discovery";
import { ApiError } from "../api/health";

export function DiscoveryPage() {
  const navigate = useNavigate();
  const [industry, setIndustry] = useState("Hotel");
  const [location, setLocation] = useState("Sicilia");
  const [maxResults, setMaxResults] = useState(20);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const run = await createDiscovery({
        industry,
        location,
        max_results: maxResults,
      });
      navigate(`/discoveries/${run.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Discovery non avviata.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
      <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-12">
        <header className="space-y-2">
          <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">Discovery</p>
          <h1 className="text-4xl font-semibold tracking-tight">Trova aziende</h1>
          <p className="max-w-xl text-stone-600">
            Cerca per settore e località. Il primo provider è OpenStreetMap: nessuna API key.
            I siti trovati si possono poi analizzare con lo stesso motore M1/M2.
          </p>
        </header>

        <form
          onSubmit={(event) => void onSubmit(event)}
          className="space-y-4 rounded-2xl border border-stone-200 bg-white p-6 shadow-sm"
        >
          <div>
            <label htmlFor="industry" className="text-sm font-medium text-stone-700">
              Settore
            </label>
            <input
              id="industry"
              value={industry}
              onChange={(event) => setIndustry(event.target.value)}
              placeholder="es. Hotel"
              className="mt-2 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
              disabled={submitting}
            />
          </div>
          <div>
            <label htmlFor="location" className="text-sm font-medium text-stone-700">
              Località
            </label>
            <input
              id="location"
              value={location}
              onChange={(event) => setLocation(event.target.value)}
              placeholder="es. Sicilia"
              className="mt-2 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
              disabled={submitting}
            />
          </div>
          <div>
            <label htmlFor="max" className="text-sm font-medium text-stone-700">
              Max risultati
            </label>
            <input
              id="max"
              type="number"
              min={1}
              max={50}
              value={maxResults}
              onChange={(event) => setMaxResults(Number(event.target.value))}
              className="mt-2 w-32 rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
              disabled={submitting}
            />
          </div>
          <button
            type="submit"
            disabled={submitting || industry.trim().length < 2 || location.trim().length < 2}
            className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
          >
            {submitting ? "Avvio…" : "Avvia ricerca"}
          </button>
          {error ? (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
          ) : null}
        </form>

        <p className="text-sm text-stone-500">
          <Link to="/companies" className="underline hover:text-stone-900">
            Vedi tutte le aziende salvate
          </Link>
        </p>
      </main>
  );
}
