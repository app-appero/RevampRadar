import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import {
  composeLocation,
  createDiscovery,
  fetchDiscoveryCatalog,
  fetchOsmPreview,
  formatOsmTags,
} from "../api/discovery";
import { ApiError } from "../api/health";

const STANDARD_MAX = 50;
const EXTENDED_MAX = 200;
const SELECT_CLASS =
  "mt-2 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-stone-900 disabled:bg-stone-100 disabled:text-stone-400";

export function DiscoveryPage() {
  const navigate = useNavigate();
  const [industry, setIndustry] = useState("");
  const [sectorQuery, setSectorQuery] = useState("");
  const [sectorOpen, setSectorOpen] = useState(false);
  const [region, setRegion] = useState("");
  const [province, setProvince] = useState("");
  const [city, setCity] = useState("");
  const [maxResults, setMaxResults] = useState(20);
  const [extended, setExtended] = useState(false);
  const [requireContactable, setRequireContactable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const sectorRef = useRef<HTMLDivElement | null>(null);
  const cap = extended ? EXTENDED_MAX : STANDARD_MAX;
  const catalog = useQuery({
    queryKey: ["discovery-catalog"],
    queryFn: fetchDiscoveryCatalog,
  });
  const preview = useQuery({
    queryKey: ["osm-preview", industry],
    queryFn: () => fetchOsmPreview(industry),
  });

  const regions = catalog.data?.regions ?? [];
  const sectors = catalog.data?.sectors ?? [];
  const filteredSectors = useMemo(() => {
    const needle = sectorQuery.trim().toLocaleLowerCase("it");
    if (!needle) {
      return sectors;
    }
    return sectors.filter((item) => item.toLocaleLowerCase("it").includes(needle));
  }, [sectors, sectorQuery]);
  const sectorLabel = industry || "Tutti i settori";
  const selectedRegion = useMemo(
    () => regions.find((item) => item.name === region) ?? null,
    [regions, region],
  );
  const provinces = selectedRegion?.provinces ?? [];
  const selectedProvince = useMemo(
    () => provinces.find((item) => item.name === province) ?? null,
    [provinces, province],
  );
  const cities = selectedProvince?.cities ?? [];
  const locationLabel = composeLocation(region, province, city);
  const broadArea = !city && (region || !province);

  useEffect(() => {
    if (!sectorOpen) {
      return;
    }
    function onPointerDown(event: MouseEvent) {
      if (!sectorRef.current?.contains(event.target as Node)) {
        setSectorOpen(false);
        setSectorQuery("");
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [sectorOpen]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const run = await createDiscovery({
        industry,
        location: locationLabel,
        region,
        province,
        city,
        max_results: Math.min(maxResults, cap),
        extended,
        require_contactable: requireContactable,
      });
      navigate(`/discoveries/${run.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Discovery non avviata.");
    } finally {
      setSubmitting(false);
    }
  }

  function onExtendedChange(checked: boolean) {
    setExtended(checked);
    if (checked && maxResults <= 20) {
      setMaxResults(100);
    }
    if (!checked && maxResults > STANDARD_MAX) {
      setMaxResults(STANDARD_MAX);
    }
  }

  function onRegionChange(value: string) {
    setRegion(value);
    setProvince("");
    setCity("");
  }

  function onProvinceChange(value: string) {
    setProvince(value);
    setCity("");
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-12">
      <header className="space-y-2">
        <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">Discovery</p>
        <h1 className="text-4xl font-semibold tracking-tight">Trova aziende</h1>
        <p className="max-w-xl text-stone-600">
          Settore, regione, provincia e città sono tutti opzionali. Vuoto = ricerca universale
          (tutti i settori commerciali OSM, oppure tutta Italia). I siti trovati si analizzano con
          lo stesso motore M1/M2. Le coordinate alimentano la{" "}
          <Link to="/map" className="underline">
            mappa
          </Link>
          .
        </p>
      </header>

      <form
        onSubmit={(event) => void onSubmit(event)}
        className="space-y-4 rounded-2xl border border-stone-200 bg-white p-6 shadow-sm"
      >
        <div ref={sectorRef} className="relative">
          <label htmlFor="industry" className="text-sm font-medium text-stone-700">
            Settore
          </label>
          <button
            id="industry"
            type="button"
            disabled={submitting || catalog.isLoading}
            onClick={() => {
              setSectorOpen((open) => !open);
              setSectorQuery("");
            }}
            className={`${SELECT_CLASS} flex items-center justify-between text-left`}
            aria-haspopup="listbox"
            aria-expanded={sectorOpen}
          >
            <span>{sectorLabel}</span>
            <span className="text-stone-400" aria-hidden>
              ▾
            </span>
          </button>
          {sectorOpen ? (
            <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-stone-300 bg-white shadow-lg">
              <input
                type="search"
                value={sectorQuery}
                onChange={(event) => setSectorQuery(event.target.value)}
                placeholder="Cerca settore…"
                autoFocus
                className="w-full border-b border-stone-200 px-3 py-2 text-sm outline-none"
                aria-label="Cerca settore"
              />
              <ul role="listbox" className="max-h-56 overflow-y-auto py-1 text-sm">
                <li>
                  <button
                    type="button"
                    role="option"
                    aria-selected={!industry}
                    onClick={() => {
                      setIndustry("");
                      setSectorOpen(false);
                      setSectorQuery("");
                    }}
                    className={`block w-full px-3 py-2 text-left hover:bg-stone-100 ${
                      !industry ? "bg-stone-50 font-medium" : ""
                    }`}
                  >
                    Tutti i settori
                  </button>
                </li>
                {filteredSectors.map((item) => (
                  <li key={item}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={industry === item}
                      onClick={() => {
                        setIndustry(item);
                        setSectorOpen(false);
                        setSectorQuery("");
                      }}
                      className={`block w-full px-3 py-2 text-left hover:bg-stone-100 ${
                        industry === item ? "bg-stone-50 font-medium" : ""
                      }`}
                    >
                      {item}
                    </button>
                  </li>
                ))}
                {filteredSectors.length === 0 ? (
                  <li className="px-3 py-2 text-stone-500">Nessun settore trovato.</li>
                ) : null}
              </ul>
            </div>
          ) : null}
          <p className="mt-1 text-xs text-stone-500">
            {industry
              ? preview.data?.mapped
                ? `Tag OSM: ${formatOsmTags(preview.data.tags)}`
                : preview.isPending || preview.isFetching
                  ? "Traduco il settore in tag OpenStreetMap…"
                  : "Settore non mappato."
              : `Tutti i tag commerciali OSM${preview.data?.tags?.length ? `: ${formatOsmTags(preview.data.tags)}` : ""}.`}
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label htmlFor="region" className="text-sm font-medium text-stone-700">
              Regione
            </label>
            <select
              id="region"
              value={region}
              onChange={(event) => onRegionChange(event.target.value)}
              className={SELECT_CLASS}
              disabled={submitting || catalog.isLoading}
            >
              <option value="">Tutta Italia</option>
              {regions.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="province" className="text-sm font-medium text-stone-700">
              Provincia
            </label>
            <select
              id="province"
              value={province}
              onChange={(event) => onProvinceChange(event.target.value)}
              className={SELECT_CLASS}
              disabled={submitting || !region}
            >
              <option value="">{region ? "Tutta la regione" : "Scegli prima la regione"}</option>
              {provinces.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="city" className="text-sm font-medium text-stone-700">
              Città
            </label>
            <select
              id="city"
              value={city}
              onChange={(event) => setCity(event.target.value)}
              className={SELECT_CLASS}
              disabled={submitting || !province}
            >
              <option value="">{province ? "Tutta la provincia" : "Scegli prima la provincia"}</option>
              {cities.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
        </div>
        <p className="text-xs text-stone-500">
          Località inviata: {locationLabel}
          {broadArea
            ? ". Su regione o Italia Overpass può andare in timeout: meglio una città."
            : "."}
        </p>

        <label className="flex items-start gap-3 rounded-xl border border-stone-200 bg-stone-50 px-3 py-3 text-sm">
          <input
            type="checkbox"
            checked={extended}
            onChange={(event) => onExtendedChange(event.target.checked)}
            className="mt-0.5"
            disabled={submitting}
          />
          <span>
            <span className="font-medium text-stone-800">Ricerca estesa</span>
            <span className="mt-1 block text-stone-600">
              Include attività senza sito (spesso i prospect migliori) e alza il tetto a {EXTENDED_MAX}{" "}
              risultati.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-3 rounded-xl border border-stone-200 bg-stone-50 px-3 py-3 text-sm">
          <input
            type="checkbox"
            checked={requireContactable}
            onChange={(event) => setRequireContactable(event.target.checked)}
            className="mt-0.5"
            disabled={submitting}
          />
          <span>
            <span className="font-medium text-stone-800">Escludi attività incontattabili</span>
            <span className="mt-1 block text-stone-600">
              Non salvare chi non ha né telefono, né email, né social, né sito: senza nessuno di
              questi non hai modo di contattarli.
            </span>
          </span>
        </label>
        <div>
          <label htmlFor="max" className="text-sm font-medium text-stone-700">
            Max risultati
          </label>
          <input
            id="max"
            type="number"
            min={1}
            max={cap}
            value={maxResults}
            onChange={(event) => setMaxResults(Number(event.target.value))}
            className="mt-2 w-32 rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-900"
            disabled={submitting}
          />
          <p className="mt-1 text-xs text-stone-500">
            Fino a {cap}
            {extended ? " (estesa)" : ""}.
          </p>
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
        >
          {submitting ? "Avvio…" : "Avvia ricerca"}
        </button>
        {catalog.isError ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            Catalogo settori/territori non disponibile.
          </p>
        ) : null}
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
