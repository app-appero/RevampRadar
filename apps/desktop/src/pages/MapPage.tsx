import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { backfillMapCoords, fetchMap, type MapPoint } from "../api/map";
import { ApiError } from "../api/health";
import { PageBackLink } from "../components/HistoryNav";

const CLUSTER_COLORS = ["#0f766e", "#a16207", "#7c3aed", "#be123c", "#0369a1", "#4d7c0f"];

type MapFilter = "all" | "no_site" | "with_site" | "with_app";

export function MapPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const autoBackfill = useRef(false);
  const [selectedCluster, setSelectedCluster] = useState<number | null>(null);
  const [filter, setFilter] = useState<MapFilter>("all");
  const [hideUncontactable, setHideUncontactable] = useState(false);
  const query = useQuery({
    queryKey: ["map"],
    queryFn: fetchMap,
  });
  const backfill = useMutation({
    mutationFn: backfillMapCoords,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["map"] });
    },
  });

  useEffect(() => {
    if (autoBackfill.current) {
      return;
    }
    if ((query.data?.unmapped_count ?? 0) > 0 && !backfill.isPending) {
      autoBackfill.current = true;
      backfill.mutate();
    }
  }, [query.data?.unmapped_count, backfill]);

  const noSiteCount = useMemo(
    () => (query.data?.points ?? []).filter((item) => !item.has_website).length,
    [query.data],
  );

  const visiblePoints = useMemo(() => {
    let points = query.data?.points ?? [];
    if (filter === "no_site") {
      points = points.filter((item) => !item.has_website);
    } else if (filter === "with_site") {
      points = points.filter((item) => item.has_website);
    } else if (filter === "with_app") {
      points = points.filter((item) => item.has_app);
    }
    if (hideUncontactable) {
      points = points.filter((item) => item.is_contactable);
    }
    if (selectedCluster === null) {
      return points;
    }
    return points.filter((item) => item.cluster_id === selectedCluster);
  }, [query.data, selectedCluster, filter, hideUncontactable]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) {
      return;
    }
    const map = L.map(el, { scrollWheelZoom: true }).setView([41.9, 12.5], 6);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);
    requestAnimationFrame(() => map.invalidateSize());
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }
    const group = L.featureGroup();
    for (const point of visiblePoints) {
      const marker = L.circleMarker([point.latitude, point.longitude], {
        radius: point.has_app ? 9 : point.has_website ? 7 : 8,
        color: pointColor(point),
        weight: point.has_website ? 2 : 2,
        dashArray: point.has_website ? undefined : "4 3",
        fillColor: pointColor(point),
        fillOpacity: 0.85,
      });
      marker.bindPopup(popupHtml(point));
      marker.on("popupopen", () => {
        const link = document.querySelector<HTMLAnchorElement>(`a[data-company="${point.company_id}"]`);
        link?.addEventListener("click", (event) => {
          event.preventDefault();
          void navigate(`/companies/${point.company_id}`);
        });
      });
      marker.addTo(group);
    }
    group.addTo(map);
    if (visiblePoints.length > 0) {
      map.fitBounds(group.getBounds().pad(0.2), { maxZoom: 12, animate: true });
    } else {
      map.setView([41.9, 12.5], 6);
    }
    return () => {
      map.removeLayer(group);
    };
  }, [visiblePoints, navigate]);

  const data = query.data;
  const error =
    query.error instanceof ApiError
      ? query.error.message
      : query.isError
        ? "Mappa non disponibile."
        : backfill.error instanceof ApiError
          ? backfill.error.message
          : backfill.isError
            ? "Recupero coordinate non riuscito."
            : null;

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-8">
      <header className="space-y-2">
        <PageBackLink fallback="/" label="Indietro" />
        <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">Territorio</p>
        <h1 className="text-4xl font-semibold tracking-tight">Mappa opportunità</h1>
        <p className="max-w-2xl text-stone-600">
          Punti da OpenStreetMap, colorati per Opportunity Score. I gruppi sono geografici (k-means su
          lat/lon): descrivono cosa c&apos;è in zona, non la probabilità che un cliente accetti.
        </p>
      </header>

      {error ? (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
      ) : null}

      {data && data.unmapped_count > 0 ? (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <p>
            {data.unmapped_count} aziend{data.unmapped_count === 1 ? "a" : "e"} senza coordinate.
            {backfill.isPending
              ? " Recupero lat/lon da OpenStreetMap…"
              : " Puoi recuperarle dagli id OSM già salvati, senza rifare tutta la discovery."}
          </p>
          <button
            type="button"
            disabled={backfill.isPending}
            onClick={() => backfill.mutate()}
            className="rounded-lg bg-amber-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
          >
            {backfill.isPending ? "Recupero…" : "Recupera coordinate"}
          </button>
          {backfill.isSuccess ? (
            <span className="text-xs">
              Aggiornate {backfill.data.updated}
              {backfill.data.remaining ? ` · ne restano ${backfill.data.remaining}` : ""}
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
          <div ref={containerRef} className="rr-map h-[70vh] min-h-[28rem] w-full" />
        </section>
        <aside className="space-y-4">
          <div className="rounded-2xl border border-stone-200 bg-white p-4 text-sm shadow-sm">
            <p className="font-medium text-stone-800">Legenda</p>
            <div className="mt-2 flex flex-wrap gap-1">
              {(
                [
                  ["all", "Tutti"],
                  ["no_site", noSiteCount ? `Senza sito (${noSiteCount})` : "Senza sito"],
                  ["with_site", "Con sito"],
                  ["with_app", "Con app"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setFilter(id)}
                  className={`rounded-full px-2.5 py-1 text-xs ${
                    filter === id ? "bg-stone-900 text-white" : "bg-stone-100 text-stone-700"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <label className="mt-2 flex items-center gap-2 text-xs text-stone-700">
              <input
                type="checkbox"
                checked={hideUncontactable}
                onChange={(event) => setHideUncontactable(event.target.checked)}
              />
              Nascondi incontattabili (niente sito, telefono, email o social)
            </label>
            <ul className="mt-3 space-y-1 text-stone-600">
              <li>
                <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full bg-red-700" />
                HIGH / VERY_HIGH
              </li>
              <li>
                <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full bg-amber-600" />
                MEDIUM
              </li>
              <li>
                <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full bg-stone-500" />
                LOW o senza score
              </li>
              <li>
                <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full border border-dashed border-sky-700 bg-sky-600" />
                Senza sito
              </li>
            </ul>
            <p className="mt-3 text-xs text-stone-500">
              {data
                ? `${visiblePoints.length} pin visibili · ${data.mapped_count} totali`
                : query.isLoading
                  ? "Caricamento…"
                  : "Nessun pin"}
            </p>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-stone-800">Gruppi geografici</p>
              {selectedCluster !== null ? (
                <button
                  type="button"
                  className="text-xs text-stone-500 underline"
                  onClick={() => setSelectedCluster(null)}
                >
                  Mostra tutti
                </button>
              ) : null}
            </div>
            {(data?.clusters ?? []).length === 0 ? (
              <p className="rounded-xl border border-dashed border-stone-300 bg-white px-3 py-4 text-sm text-stone-500">
                Nessun punto sulla mappa. Se hai già delle aziende, usa «Recupera coordinate». Altrimenti{" "}
                <Link to="/discovery" className="underline">
                  avvia una discovery
                </Link>{" "}
                su una città (es. Palermo), non su un&apos;intera regione.
              </p>
            ) : (
              data?.clusters.map((cluster) => (
                <button
                  key={cluster.id}
                  type="button"
                  onClick={() => setSelectedCluster(cluster.id)}
                  className={`w-full rounded-xl border px-3 py-3 text-left text-sm shadow-sm ${
                    selectedCluster === cluster.id
                      ? "border-stone-900 bg-stone-50"
                      : "border-stone-200 bg-white hover:border-stone-400"
                  }`}
                >
                  <span className="flex items-start gap-2">
                    <span
                      className="mt-1 inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: CLUSTER_COLORS[cluster.id % CLUSTER_COLORS.length] }}
                    />
                    <span>
                      <span className="font-medium text-stone-900">{cluster.label}</span>
                      <span className="mt-1 block text-xs text-stone-500">
                        {cluster.size} aziend{cluster.size === 1 ? "a" : "e"}
                        {cluster.avg_opportunity_score != null
                          ? ` · media OS ${cluster.avg_opportunity_score}`
                          : ""}
                        {` · ${Math.round(cluster.high_share * 100)}% HIGH`}
                        {` · ${Math.round(cluster.app_share * 100)}% con app`}
                        <span
                          className={
                            (cluster.no_site_share ?? 0) > 0 ? "text-sky-800" : undefined
                          }
                        >
                          {` · ${Math.round((cluster.no_site_share ?? 0) * 100)}% senza sito`}
                        </span>
                      </span>
                    </span>
                  </span>
                </button>
              ))
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}

function pointColor(point: MapPoint): string {
  if (!point.has_website) {
    return "#0284c7";
  }
  if (point.priority === "VERY_HIGH" || point.priority === "HIGH") {
    return "#b91c1c";
  }
  if (point.priority === "MEDIUM") {
    return "#d97706";
  }
  if (point.priority === "LOW") {
    return "#57534e";
  }
  return "#a8a29e";
}

function popupHtml(point: MapPoint): string {
  const score = point.opportunity_score != null ? String(point.opportunity_score) : "—";
  const city = point.city ? escapeHtml(point.city) : "Città n/d";
  const category = point.category ? escapeHtml(point.category) : "";
  const app = point.has_app ? " · app" : "";
  const siteLine = point.has_website
    ? ""
    : `<p style="color:#0369a1;font-weight:600">Senza sito</p>`;
  return `
    <div class="text-sm">
      <p class="font-semibold">${escapeHtml(point.name)}</p>
      <p>${city}${category ? ` · ${category}` : ""}</p>
      ${siteLine}
      <p>Opportunity ${score}${point.priority ? ` · ${escapeHtml(point.priority)}` : ""}${app}</p>
      <p class="mt-1"><a data-company="${point.company_id}" href="/companies/${point.company_id}">Apri azienda</a></p>
    </div>
  `;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
