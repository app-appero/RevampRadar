import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import {
  composeLocation,
  createDiscovery,
  fetchDiscovery,
  fetchDiscoveryCatalog,
  fetchRecentDiscoveries,
  fetchOsmPreview,
  formatOsmTags,
} from "../api/discovery";
import { ApiError } from "../api/health";

const STANDARD_MAX = 50;
const EXTENDED_MAX = 200;
const SELECT_CLASS =
  "mt-2 h-12 w-full rounded-xl border border-stone-300 bg-white px-3.5 text-base outline-none focus:border-stone-900 disabled:bg-stone-100 disabled:text-stone-400 md:h-auto md:rounded-lg md:px-3 md:py-2 md:text-sm";

export function DiscoveryPage() {
  const navigate = useNavigate();
  const [industry, setIndustry] = useState("");
  const [sectorQuery, setSectorQuery] = useState("");
  const [sectorOpen, setSectorOpen] = useState(false);
  const [region, setRegion] = useState("");
  const [province, setProvince] = useState("");
  const [city, setCity] = useState("");
  const [maxResults, setMaxResults] = useState(EXTENDED_MAX);
  const [extended, setExtended] = useState(true);
  const [requireContactable, setRequireContactable] = useState(true);
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
    setMaxResults(checked ? EXTENDED_MAX : STANDARD_MAX);
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
    <main className="mx-auto flex max-w-3xl flex-col gap-5 px-5 pt-4 pb-8 md:gap-8 md:px-6 md:py-12">
      <header className="space-y-2">
        <p className="hidden text-sm font-medium tracking-wide text-stone-500 uppercase md:block">Discovery</p>
        <h1 className="text-[28px] leading-tight font-semibold tracking-tight md:text-4xl">
          <span className="md:hidden">Discovery</span>
          <span className="hidden md:inline">Trova aziende</span>
        </h1>
        <p className="hidden max-w-xl text-stone-600 md:block">
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
        className="space-y-4 rounded-2xl border border-stone-200 bg-white p-4 shadow-sm md:p-6"
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
          <p className="mt-1 hidden text-xs text-stone-500 md:block">
            {industry
              ? preview.data?.mapped
                ? `Tag OSM: ${formatOsmTags(preview.data.tags)}`
                : preview.isPending || preview.isFetching
                  ? "Traduco il settore in tag OpenStreetMap…"
                  : "Settore non mappato."
              : `Tutti i tag commerciali OSM${preview.data?.tags?.length ? `: ${formatOsmTags(preview.data.tags)}` : ""}.`}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4">
          <div className="col-span-2 sm:col-span-1">
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
        <p className="hidden text-xs text-stone-500 md:block">
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
            <span className="mt-1 hidden text-stone-600 md:block">
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
            <span className="mt-1 hidden text-stone-600 md:block">
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
          <p className="mt-1 hidden text-xs text-stone-500 md:block">
            Fino a {cap}
            {extended ? " (estesa)" : ""}.
          </p>
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="h-[50px] rounded-xl bg-stone-900 px-4 text-base font-semibold text-white hover:bg-stone-800 disabled:opacity-50 md:h-auto md:rounded-lg md:py-2 md:text-sm md:font-medium"
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

      <LastSearch />

      <p className="hidden text-sm text-stone-500 md:block">
        <Link to="/companies" className="underline hover:text-stone-900">
          Vedi tutte le aziende salvate
        </Link>
      </p>
    </main>
  );
}

/** Mobile: ultima ricerca con avanzamento e aziende trovate (come da canvas). */
function LastSearch() {
  const [segment, setSegment] = useState<"all" | "refactor" | "greenfield">("all");
  const recent = useQuery({
    queryKey: ["recent-discoveries", 1],
    queryFn: () => fetchRecentDiscoveries(1),
    refetchInterval: (query) =>
      query.state.data?.some((item) => item.status === "queued" || item.status === "running") ? 2000 : false,
  });
  const last = recent.data?.[0];
  const detail = useQuery({
    queryKey: ["discovery", last?.id],
    queryFn: () => fetchDiscovery(last!.id),
    enabled: Boolean(last),
  });
  if (!last) return null;
  const running = last.status === "queued" || last.status === "running";
  const percent = running ? (last.progress_percent ?? 0) : 100;
  const companies = (detail.data?.companies ?? []).filter((company) => {
    if (segment === "all") return true;
    return Boolean(company.website_url || company.domain) === (segment === "refactor");
  });
  return (
    <section className="flex flex-col gap-2.5 md:hidden">
      <div className="flex items-baseline justify-between">
        <h2 className="text-base font-semibold">Ultima ricerca</h2>
        <span className="text-xs text-stone-600">
          {last.industry} · {last.location}
        </span>
      </div>
      <Link to={`/discoveries/${last.id}`} className="flex flex-col gap-2 rounded-[14px] border border-stone-200 bg-white p-3.5">
        <div className="flex justify-between text-[13px] text-stone-700">
          <span>{running ? "Ricerca in corso" : "Ricerca completata"}</span>
          <span className="font-semibold">{last.total_found} aziende</span>
        </div>
        <div className="h-2 rounded bg-stone-200">
          <div className="h-2 rounded bg-stone-900" style={{ width: `${percent}%` }} />
        </div>
      </Link>
      <div className="flex gap-2">
        {(
          [
            ["all", "Tutte"],
            ["refactor", "Da rifare"],
            ["greenfield", "Da creare"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setSegment(value)}
            className={`shrink-0 rounded-full px-3.5 py-2 text-[13px] font-medium ${
              segment === value ? "bg-stone-900 text-white" : "bg-stone-100 text-stone-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {companies.slice(0, 8).map((company) => {
        const hasSite = Boolean(company.website_url || company.domain);
        return (
          <Link
            key={company.id}
            to={`/companies/${company.id}`}
            className="flex items-center gap-3 rounded-[14px] border border-stone-200 bg-white px-3.5 py-3"
          >
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <strong className="truncate text-[15px]">{company.name}</strong>
              <span className="truncate text-xs text-stone-600">
                {hasSite ? (company.domain ?? company.website_url) : "Nessun sito · Da creare"}
              </span>
            </span>
            <span className="shrink-0 rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-semibold text-stone-700">
              {hasSite ? "Da rifare" : "Da creare"}
            </span>
          </Link>
        );
      })}
    </section>
  );
}
