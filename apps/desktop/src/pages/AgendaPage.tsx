import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  ACTIVITY_LABELS,
  completeActivity,
  fetchAgenda,
  type AgendaItem,
} from "../api/crm";
import { ApiError } from "../api/health";

const WEEKDAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function endOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0, 23, 59, 59, 999);
}

function addMonths(date: Date, months: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function dayKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function toApiIso(date: Date): string {
  return date.toISOString();
}

function calendarCells(month: Date): (Date | null)[] {
  const first = startOfMonth(month);
  const last = endOfMonth(month);
  const startOffset = (first.getDay() + 6) % 7;
  const cells: (Date | null)[] = Array.from({ length: startOffset }, () => null);
  for (let day = 1; day <= last.getDate(); day += 1) {
    cells.push(new Date(month.getFullYear(), month.getMonth(), day));
  }
  while (cells.length % 7 !== 0) {
    cells.push(null);
  }
  return cells;
}

function formatMonthTitle(date: Date): string {
  return date.toLocaleDateString("it-IT", { month: "long", year: "numeric" });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("it-IT", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function groupByDay(items: AgendaItem[]): Map<string, AgendaItem[]> {
  const map = new Map<string, AgendaItem[]>();
  for (const item of items) {
    const key = dayKey(new Date(item.due_at));
    const list = map.get(key) ?? [];
    list.push(item);
    map.set(key, list);
  }
  return map;
}

export function AgendaPage() {
  const queryClient = useQueryClient();
  const [month, setMonth] = useState(() => startOfMonth(new Date()));
  const [selectedDay, setSelectedDay] = useState<Date | null>(() => new Date());
  const [error, setError] = useState<string | null>(null);

  const rangeFrom = startOfMonth(month);
  const rangeTo = endOfMonth(month);

  const agendaQuery = useQuery({
    queryKey: ["agenda", rangeFrom.toISOString(), rangeTo.toISOString()],
    queryFn: () =>
      fetchAgenda({
        from: toApiIso(rangeFrom),
        to: toApiIso(rangeTo),
        include_overdue: true,
      }),
  });

  const completeMutation = useMutation({
    mutationFn: completeActivity,
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["agenda"] });
      void queryClient.invalidateQueries({ queryKey: ["company-opportunity"] });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Completamento non riuscito.");
    },
  });

  const items = agendaQuery.data ?? [];
  const byDay = useMemo(() => groupByDay(items), [items]);
  const overdue = useMemo(() => items.filter((item) => item.is_overdue), [items]);
  const selectedItems = useMemo(() => {
    if (!selectedDay) return items;
    return byDay.get(dayKey(selectedDay)) ?? [];
  }, [byDay, items, selectedDay]);

  const cells = useMemo(() => calendarCells(month), [month]);
  const today = new Date();

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-10">
      <header className="space-y-2">
        <p className="text-sm font-medium tracking-wide text-stone-500 uppercase">CRM</p>
        <h1 className="text-3xl font-semibold tracking-tight">Agenda</h1>
        <p className="max-w-2xl text-stone-600">
          Pianifica richiami e meeting con le aziende in pipeline. Segna come fatto quando hai
          contattato il cliente.
        </p>
      </header>

      {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <section className="rounded-2xl border border-stone-200 bg-white p-4">
          <div className="mb-4 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setMonth((current) => addMonths(current, -1))}
              className="rounded-lg border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-50"
            >
              ←
            </button>
            <h2 className="text-lg font-medium capitalize">{formatMonthTitle(month)}</h2>
            <button
              type="button"
              onClick={() => setMonth((current) => addMonths(current, 1))}
              className="rounded-lg border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-50"
            >
              →
            </button>
          </div>

          <div className="mb-2 grid grid-cols-7 gap-1 text-center text-xs font-medium text-stone-500">
            {WEEKDAYS.map((label) => (
              <div key={label} className="py-1">
                {label}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-1">
            {cells.map((day, index) => {
              if (!day) {
                return <div key={`empty-${index}`} className="aspect-square" />;
              }
              const key = dayKey(day);
              const count = byDay.get(key)?.length ?? 0;
              const selected = selectedDay ? isSameDay(day, selectedDay) : false;
              const isToday = isSameDay(day, today);
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSelectedDay(day)}
                  className={`flex aspect-square flex-col items-center justify-center rounded-lg border text-sm transition ${
                    selected
                      ? "border-stone-900 bg-stone-900 text-white"
                      : isToday
                        ? "border-amber-400 bg-amber-50 text-stone-900"
                        : "border-stone-200 bg-stone-50 text-stone-800 hover:border-stone-400"
                  }`}
                >
                  <span>{day.getDate()}</span>
                  {count > 0 ? (
                    <span
                      className={`mt-0.5 h-1.5 w-1.5 rounded-full ${
                        selected ? "bg-white" : "bg-stone-900"
                      }`}
                    />
                  ) : null}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={() => {
              const now = new Date();
              setMonth(startOfMonth(now));
              setSelectedDay(now);
            }}
            className="mt-4 text-sm text-stone-600 underline hover:text-stone-900"
          >
            Vai a oggi
          </button>
        </section>

        <section className="space-y-6">
          {overdue.length > 0 ? (
            <div className="space-y-2">
              <h2 className="text-sm font-medium tracking-wide text-red-700 uppercase">
                In ritardo ({overdue.length})
              </h2>
              <ul className="space-y-2">
                {overdue.map((item) => (
                  <AgendaCard
                    key={item.id}
                    item={item}
                    onComplete={() => completeMutation.mutate(item.id)}
                    pending={completeMutation.isPending}
                  />
                ))}
              </ul>
            </div>
          ) : null}

          <div className="space-y-2">
            <h2 className="text-sm font-medium tracking-wide text-stone-500 uppercase">
              {selectedDay
                ? selectedDay.toLocaleDateString("it-IT", {
                    weekday: "long",
                    day: "numeric",
                    month: "long",
                  })
                : "Attività del mese"}
            </h2>
            {agendaQuery.isLoading ? (
              <p className="text-sm text-stone-500">Caricamento…</p>
            ) : selectedItems.length === 0 ? (
              <p className="rounded-xl border border-dashed border-stone-300 px-4 py-8 text-center text-sm text-stone-500">
                Nessuna attività pianificata.
                <br />
                Dalla scheda azienda puoi aggiungere un richiamo o un meeting.
              </p>
            ) : (
              <ul className="space-y-2">
                {selectedItems.map((item) => (
                  <AgendaCard
                    key={item.id}
                    item={item}
                    onComplete={() => completeMutation.mutate(item.id)}
                    pending={completeMutation.isPending}
                  />
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function AgendaCard({
  item,
  onComplete,
  pending,
}: {
  item: AgendaItem;
  onComplete: () => void;
  pending: boolean;
}) {
  return (
    <li className="rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="font-medium">
            <Link to={`/companies/${item.company_id}`} className="hover:underline">
              {item.company_name}
            </Link>
          </p>
          <p className="text-stone-700">
            {ACTIVITY_LABELS[item.type] ?? item.type}
            {item.note ? ` — ${item.note}` : ""}
          </p>
          <p className={`text-xs ${item.is_overdue ? "text-red-700" : "text-stone-500"}`}>
            {formatTime(item.due_at)}
          </p>
        </div>
        <button
          type="button"
          disabled={pending}
          onClick={onComplete}
          className="shrink-0 rounded-lg border border-stone-300 px-3 py-1.5 text-xs font-medium hover:bg-stone-50 disabled:opacity-50"
        >
          Fatto
        </button>
      </div>
    </li>
  );
}
