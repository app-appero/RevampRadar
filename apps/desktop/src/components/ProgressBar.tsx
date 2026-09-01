type ProgressBarProps = {
  percent: number;
  label: string;
  hint?: string;
};

export function ProgressBar({ percent, label, hint }: ProgressBarProps) {
  const value = Math.min(100, Math.max(0, Math.round(percent)));
  return (
    <div className="space-y-2 rounded-lg bg-amber-50 px-3 py-3">
      <div className="flex items-center justify-between gap-3 text-sm text-amber-900">
        <span>{label}</span>
        <span className="font-medium tabular-nums">{value}%</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-amber-200"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        aria-label="Avanzamento"
      >
        <div
          className="h-full rounded-full bg-amber-700 transition-[width] duration-500"
          style={{ width: `${value}%` }}
        />
      </div>
      {hint ? <p className="text-xs text-amber-800/80">{hint}</p> : null}
    </div>
  );
}
