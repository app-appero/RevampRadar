import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { fetchCompanyAuditHistory, type CompanyAuditHistoryItem } from "../api/audits";

const SCORE_COLUMNS: { label: string; key: keyof CompanyAuditHistoryItem }[] = [
  { label: "Website", key: "website_score" },
  { label: "Tecnico", key: "technical_score" },
  { label: "Performance", key: "performance_score" },
  { label: "UI", key: "ui_score" },
  { label: "UX", key: "ux_score" },
  { label: "Mobile", key: "mobile_score" },
  { label: "Conversione", key: "conversion_score" },
  { label: "SEO", key: "seo_score" },
  { label: "Trust", key: "trust_score" },
  { label: "Business", key: "business_score" },
  { label: "Opportunity", key: "opportunity_score" },
];

export function CompanyAuditHistory({
  companyId,
  currentAuditId,
}: {
  companyId: string;
  currentAuditId?: string;
}) {
  const historyQuery = useQuery({
    queryKey: ["company-audit-history", companyId],
    queryFn: () => fetchCompanyAuditHistory(companyId),
  });

  if (historyQuery.isLoading) {
    return <p className="text-sm text-stone-500">Caricamento storico audit…</p>;
  }
  if (historyQuery.isError) {
    return <p className="text-sm text-red-700">Impossibile caricare lo storico degli audit.</p>;
  }
  const audits = historyQuery.data ?? [];
  if (!audits.length) return null;
  if (currentAuditId && audits[0].id !== currentAuditId) return null;

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">Confronto audit</h2>
        <p className="text-sm text-stone-600">Audit ordinati dal più recente, con tutti gli score disponibili.</p>
      </div>
      <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white">
        <table className="w-full min-w-[1180px] text-left text-sm">
          <thead className="bg-stone-50 text-xs tracking-wide text-stone-500 uppercase">
            <tr>
              <th className="px-3 py-3">Data</th>
              {SCORE_COLUMNS.map((column) => <th key={column.key} className="px-3 py-3">{column.label}</th>)}
              <th className="px-3 py-3">Priorità</th>
              <th className="px-3 py-3">Audit</th>
            </tr>
          </thead>
          <tbody>
            {audits.map((audit) => (
              <tr key={audit.id} className="border-t border-stone-100">
                <td className="whitespace-nowrap px-3 py-3">{new Date(audit.created_at).toLocaleString("it-IT")}</td>
                {SCORE_COLUMNS.map((column) => (
                  <td key={column.key} className="px-3 py-3">{audit[column.key] ?? "—"}</td>
                ))}
                <td className="px-3 py-3">{audit.priority ?? "—"}</td>
                <td className="px-3 py-3">
                  <Link to={`/audits/${audit.id}`} className="font-medium underline">Apri</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <AuditScoreChart audits={audits} />
    </section>
  );
}

function AuditScoreChart({ audits }: { audits: CompanyAuditHistoryItem[] }) {
  const chronological = [...audits].reverse();
  const width = 720;
  const height = 230;
  const left = 44;
  const right = 14;
  const top = 18;
  const bottom = 38;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const x = (index: number) => left + (chronological.length <= 1 ? plotWidth / 2 : index * plotWidth / (chronological.length - 1));
  const y = (score: number) => top + (100 - score) * plotHeight / 100;
  const series = [
    { key: "website_score" as const, label: "Website Score", color: "#2563eb" },
    { key: "opportunity_score" as const, label: "Opportunity Score", color: "#d97706" },
  ];

  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-4">
      <div className="mb-3 flex flex-wrap gap-4 text-xs text-stone-600">
        {series.map((item) => (
          <span key={item.key} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
            {item.label}
          </span>
        ))}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Andamento degli score negli audit">
        {[0, 50, 100].map((score) => (
          <g key={score}>
            <line x1={left} x2={width - right} y1={y(score)} y2={y(score)} stroke="#44403c" />
            <text x={left - 8} y={y(score) + 4} textAnchor="end" fill="#78716c" fontSize="11">{score}</text>
          </g>
        ))}
        {series.map((item) => {
          const points = chronological
            .map((audit, index) => {
              const score = audit[item.key];
              return score == null ? null : { x: x(index), y: y(score), score, id: audit.id };
            })
            .filter((point): point is { x: number; y: number; score: number; id: string } => point !== null);
          return (
            <g key={item.key}>
              {points.length > 1 ? (
                <polyline
                  points={points.map((point) => `${point.x},${point.y}`).join(" ")}
                  fill="none"
                  stroke={item.color}
                  strokeWidth="3"
                  strokeLinejoin="round"
                />
              ) : null}
              {points.map((point) => (
                <circle key={point.id} cx={point.x} cy={point.y} r="4" fill={item.color}>
                  <title>{`${item.label}: ${point.score}`}</title>
                </circle>
              ))}
            </g>
          );
        })}
        <text x={left} y={height - 8} fill="#78716c" fontSize="11">
          {new Date(chronological[0].created_at).toLocaleDateString("it-IT")}
        </text>
        {chronological.length > 1 ? (
          <text x={width - right} y={height - 8} textAnchor="end" fill="#78716c" fontSize="11">
            {new Date(chronological[chronological.length - 1].created_at).toLocaleDateString("it-IT")}
          </text>
        ) : null}
      </svg>
    </div>
  );
}
