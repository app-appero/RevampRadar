import { Link } from "react-router-dom";

import type { Intelligence } from "../api/intelligence";

export function IntelligencePanel({ data }: { data: Intelligence }) {
  const s = data.signals;
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
          Segnali già misurati: tech, social, stelle OSM, confronto con l’audit precedente. Niente dati inventati.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Box label="Tecnologie" value={s.technologies.join(", ") || "non rilevate"} />
        <Box label="Analytics" value={s.analytics.join(", ") || "non rilevati"} />
        <Box label="Stelle OSM" value={s.osm_stars ?? "n/d"} />
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
                <a href={item.url} className="break-all underline" target="_blank" rel="noreferrer">
                  {item.url}
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
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
      ) : (
        <p className="text-sm text-stone-500">Nessun audit precedente su questo sito: niente storico da confrontare.</p>
      )}
    </section>
  );
}

function Box({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
      <p className="text-xs tracking-wide text-stone-500 uppercase">{label}</p>
      <p className="mt-1 text-sm font-medium break-all">{value}</p>
    </div>
  );
}
