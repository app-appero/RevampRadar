import { useState } from "react";

type Props = {
  label: string;
  /** Cosa verrà eliminato, mostrato prima della conferma. */
  warning: string;
  onConfirm: () => void;
  pending?: boolean;
  /** Se presente, per confermare va digitata questa parola (per le eliminazioni totali). */
  requireText?: string;
  /** Classi del contenitore (es. nascondere su mobile). */
  className?: string;
};

export function ConfirmDelete({ className, ...props }: Props) {
  return className ? (
    <div className={className}>
      <ConfirmDeleteInner {...props} />
    </div>
  ) : (
    <ConfirmDeleteInner {...props} />
  );
}

function ConfirmDeleteInner({ label, warning, onConfirm, pending, requireText }: Omit<Props, "className">) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const canConfirm = !requireText || typed.trim() === requireText;

  function close() {
    setOpen(false);
    setTyped("");
  }

  if (!open) {
    return (
      <button
        type="button"
        disabled={pending}
        onClick={() => setOpen(true)}
        className="rounded-lg border border-red-200 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
      >
        {pending ? "Elimino…" : label}
      </button>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-red-200 bg-red-50 p-3 text-left text-xs text-red-900">
      <p>{warning} L’operazione è definitiva.</p>
      {requireText ? (
        <input
          autoFocus
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          placeholder={`Scrivi ${requireText} per confermare`}
          className="w-full rounded border border-red-300 bg-white px-2 py-1 text-xs outline-none focus:border-red-600"
        />
      ) : null}
      <div className="flex gap-2">
        <button
          type="button"
          disabled={!canConfirm || pending}
          onClick={() => {
            onConfirm();
            close();
          }}
          className="rounded bg-red-700 px-2 py-1 font-medium text-white hover:bg-red-800 disabled:opacity-50"
        >
          Elimina definitivamente
        </button>
        <button type="button" onClick={close} className="rounded border border-red-300 px-2 py-1 hover:bg-red-100">
          Annulla
        </button>
      </div>
    </div>
  );
}
