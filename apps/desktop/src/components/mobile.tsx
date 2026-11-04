import type { ReactNode } from "react";

// Pezzi condivisi delle schermate mobile (vedi canvas "RevampRadar – Design Mobile").

const PRIORITY_LABELS: Record<string, string> = {
  VERY_HIGH: "Molto alta",
  HIGH: "Alta",
  MEDIUM: "Media",
  LOW: "Bassa",
};

export function priorityLabel(priority: string | null | undefined): string {
  return priority ? (PRIORITY_LABELS[priority] ?? priority) : "—";
}

/** Chip "Opportunità": verde per priorità alta, neutro altrimenti. */
export function PriorityChip({ priority, prefix }: { priority: string | null | undefined; prefix?: string }) {
  if (!priority) return null;
  const hot = priority === "HIGH" || priority === "VERY_HIGH";
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ${
        hot ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-700"
      }`}
    >
      {prefix ? `${prefix} ` : ""}
      {priorityLabel(priority)}
    </span>
  );
}

/** Chip contorno "Sito 38/100" (Website Score, distinto dall'Opportunity Score). */
export function SiteScoreChip({ score }: { score: number | null | undefined }) {
  if (score == null) return null;
  return (
    <span className="inline-flex rounded-full border border-stone-400 px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap text-stone-800">
      Sito {score}/100
    </span>
  );
}

export function MobileCard({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-stone-200 bg-white p-4 ${className}`}>{children}</div>
  );
}

export function formatRelativeDay(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  const today = new Date();
  const start = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diffDays = Math.round((start(today) - start(date)) / 86_400_000);
  const time = date.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
  if (diffDays === 0) return `Oggi, ${time}`;
  if (diffDays === 1) return "Ieri";
  return date.toLocaleDateString("it-IT", { day: "numeric", month: "short" });
}
