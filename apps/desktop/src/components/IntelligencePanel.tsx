import { Link } from "react-router-dom";

import type { Intelligence } from "../api/intelligence";
import { ExternalLink } from "./ExternalLink";

export function IntelligencePanel({ data }: { data: Intelligence }) {
  const s = data.signals;
  const appLinks = s.app_links ?? [];
  const delta = (value: number | null) => {
    if (value == null) return "—";
    if (value > 0) return `+${value}`;
    return String(value);
  };

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-medium">Intelligence</h2>
        <p className="text-sm text-stone-500">
          Niente recensioni inventate: App Store usa il feed ufficiale Apple; Play resta solo URL.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Box label="Tecnologie" value={s.technologies.join(", ") || "non rilevate"} />
        <Box label="Analytics" value={s.analytics.join(", ") || "non rilevati"} />
        <Box label="Stelle OSM" value={s.osm_stars ?? "n/d"} />
        <Box
          label="Tag OSM"
          value={
            s.osm_tags && Object.keys(s.osm_tags).length > 0
              ? Object.entries(s.osm_tags)
                  .filter(([key]) => !["start_date", "opening_hours", "stars"].includes(key))
                  .map(([key, value]) => `${key}=${value}`)
                  .join(" · ") || "n/d"
              : "n/d"
          }
        />
        <Box label="Apertura (OSM)" value={s.osm_start_date ?? "n/d"} />
        <Box label="Orari (OSM)" value={s.osm_opening_hours ?? "n/d"} />
        <Box
          label="Ultimo audit"
          value={
            data.monitoring.days_since == null
              ? "mai analizzato"
              : `${data.monitoring.days_since} giorni fa${data.monitoring.stale ? " (stale)" : ""}`
          }
        />
      </div>
      {s.aging.length > 0 ? (
        <ul className="list-disc pl-5 text-sm text-stone-700">
          {s.aging.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
      <div>
        <h3 className="text-xs tracking-wide text-stone-500 uppercase">Social sul sito</h3>
        {s.social.length === 0 ? (
          <p className="mt-2 text-sm text-stone-500">Nessun link social trovato nella homepage analizzata.</p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {s.social.map((item) => (
              <li key={item.url}>
                <span className="font-medium">{item.network}</span>{" "}
                <ExternalLink href={item.url} className="break-all underline">
                  {item.url}
                </ExternalLink>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h3 className="text-xs tracking-wide text-stone-500 uppercase">App Store / Play</h3>
        {appLinks.length === 0 ? (
          <p className="mt-2 text-sm text-stone-500">
            Nessun link App Store o Play sulla homepage. Recensioni solo da App Store, se c’è il link.
          </p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {appLinks.map((item) => (
              <li key={item.url}>
                <span className="font-medium">{storeLabel(item.store)}</span>{" "}
                <ExternalLink href={item.url} className="break-all underline">
                  {item.listing?.name ?? item.url}
                </ExternalLink>
                {item.listing ? (
                  <>
                    <p className="text-xs text-stone-500">{listingSummary(item.listing)}</p>
                    {item.listing.reviews ? <AppleReviewsBlock reviews={item.listing.reviews} /> : null}
                  </>
                ) : item.store === "play_store" ? (
                  <p className="text-xs text-stone-500">Play: solo URL, niente scraping dello store.</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
      {(s.saas ?? []).length > 0 ? (
        <div>
          <h3 className="text-xs tracking-wide text-stone-500 uppercase">SaaS / prodotto pubblico</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-stone-700">
            {(s.saas ?? []).map((note) => (
              <li key={note}>{saasLabel(note)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {data.history ? (
        <div className="rounded-2xl border border-stone-200 bg-white p-4">
          <h3 className="text-sm font-medium">Confronto con l’audit precedente</h3>
          <p className="mt-1 text-xs text-stone-500">
            <Link to={`/audits/${data.history.previous_audit_id}`} className="underline">
              Audit precedente
            </Link>
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Box label="Δ Website Score" value={delta(data.history.website_score_delta)} />
            <Box label="Δ Opportunity Score" value={delta(data.history.opportunity_score_delta)} />
          </div>
          <p className="mt-3 text-sm text-stone-700">
            Nuovi finding: {data.history.new_finding_codes.join(", ") || "nessuno"}
          </p>
          <p className="text-sm text-stone-700">
            Risolti: {data.history.resolved_finding_codes.join(", ") || "nessuno"}
          </p>
        </div>
      ) : null}
    </section>
  );
}

function AppleReviewsBlock({
  reviews,
}: {
  reviews: {
    fetched: number;
    average_rating: number | null;
    sentiment: string;
    positive_count: number;
    negative_count: number;
    themes: { code: string; label: string; count: number }[];
    samples: { rating: number | null; title: string | null; text: string }[];
  };
}) {
  return (
    <div className="mt-2 space-y-2 rounded-xl border border-stone-200 bg-stone-50 px-3 py-2">
      <p className="text-xs text-stone-600">
        {reviews.fetched} recensioni recenti (feed Apple)
        {reviews.average_rating != null ? ` · media ${reviews.average_rating}/5` : ""} ·{" "}
        {sentimentLabel(reviews.sentiment)} · {reviews.positive_count} positive · {reviews.negative_count}{" "}
        negative
      </p>
      {reviews.themes.length > 0 ? (
        <ul className="text-xs text-stone-700">
          {reviews.themes.map((theme) => (
            <li key={theme.code}>
              {theme.label} ({theme.count})
            </li>
          ))}
        </ul>
      ) : null}
      {reviews.samples.length > 0 ? (
        <ul className="space-y-1 text-xs text-stone-600">
          {reviews.samples.map((sample, index) => (
            <li key={`${sample.title ?? "r"}-${index}`}>
              {sample.rating != null ? `${sample.rating}/5` : "n/d"}
              {sample.title ? ` · ${sample.title}` : ""}
              {sample.text ? ` — ${sample.text}` : ""}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function sentimentLabel(value: string): string {
  if (value === "positive") return "sentiment positivo";
  if (value === "negative") return "sentiment negativo";
  if (value === "mixed") return "sentiment misto";
  return "sentiment n/d";
}

function listingSummary(listing: {
  average_rating: number | null;
  rating_count: number | null;
  version: string | null;
  package_id?: string | null;
  source: string;
}): string {
  if (listing.source === "play_url") {
    return listing.package_id
      ? `Play: package ${listing.package_id} · solo URL, niente scraping`
      : "Play: solo URL, niente scraping dello store.";
  }
  const parts = [
    listing.average_rating != null ? `${listing.average_rating}/5` : "rating n/d",
    listing.rating_count != null ? `${listing.rating_count} voti` : null,
    listing.version ? `v${listing.version}` : null,
    listing.source === "itunes_lookup" ? "App Store" : listing.source,
  ];
  return parts.filter(Boolean).join(" · ");
}

function saasLabel(note: string): string {
  if (note === "login_form") return "Form di login sulla homepage";
  if (note === "demo_or_trial_cta") return "CTA demo / prova gratuita";
  if (note.startsWith("product_paths:")) {
    return `Percorsi prodotto: ${note.slice("product_paths:".length)}`;
  }
  if (note.startsWith("widgets:")) {
    return `Widget: ${note.slice("widgets:".length)}`;
  }
  return note;
}

function storeLabel(store: string): string {
  if (store === "app_store") return "App Store";
  if (store === "play_store") return "Play Store";
  return store;
}

function Box({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
      <p className="text-xs tracking-wide text-stone-500 uppercase">{label}</p>
      <p className="mt-1 text-sm font-medium break-all">{value}</p>
    </div>
  );
}
