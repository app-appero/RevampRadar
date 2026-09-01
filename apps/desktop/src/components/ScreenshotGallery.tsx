import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { screenshotSrc, type AuditScreenshot } from "../api/audits";

export function ScreenshotGallery({ shots }: { shots: AuditScreenshot[] }) {
  const current = shots.filter((shot) => !isPreview(shot));
  const previews = shots.filter((shot) => isPreview(shot));
  const [lightbox, setLightbox] = useState<{ shots: AuditScreenshot[]; index: number } | null>(null);

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-lg font-medium">Screenshot</h2>
        <p className="text-sm text-stone-500">
          Clicca per ingrandire. Scorri in orizzontale: inizio pagina, contenuto e footer, desktop e mobile.
        </p>
      </div>
      {current.length > 0 ? (
        <div className="flex gap-4 overflow-x-auto pb-2">
          {current.map((shot, index) => (
            <ShotCard key={shot.id} shot={shot} onOpen={() => setLightbox({ shots: current, index })} />
          ))}
        </div>
      ) : null}

      {previews.length > 0 ? (
        <div className="space-y-3">
          <div>
            <h3 className="text-sm font-medium">Come potrebbe migliorare</h3>
            <p className="text-sm text-stone-500">
              Più viewport (inizio, contenuto, footer, mobile) con overlay indicativo: testo più
              leggibile, CTA visibile, banner cookie nascosti. Non è il restyling finale.
            </p>
          </div>
          <div className="flex gap-4 overflow-x-auto pb-2">
            {previews.map((shot, index) => (
              <ShotCard
                key={shot.id}
                shot={shot}
                caption="Dopo (indicativo)"
                onOpen={() => setLightbox({ shots: previews, index })}
              />
            ))}
          </div>
        </div>
      ) : null}

      {lightbox ? (
        <Lightbox
          shots={lightbox.shots}
          index={lightbox.index}
          onClose={() => setLightbox(null)}
          onIndex={(index) => setLightbox({ shots: lightbox.shots, index })}
        />
      ) : null}
    </section>
  );
}

function isPreview(shot: AuditScreenshot): boolean {
  return shot.preview ?? shot.device.startsWith("preview_");
}

function ShotCard({
  shot,
  caption,
  onOpen,
}: {
  shot: AuditScreenshot;
  caption?: string;
  onOpen: () => void;
}) {
  return (
    <figure className="w-72 shrink-0 overflow-hidden rounded-2xl border border-stone-200 bg-white">
      <button type="button" onClick={onOpen} className="block w-full cursor-zoom-in text-left">
        <img
          src={screenshotSrc(shot.url)}
          alt={caption ?? shot.label ?? shot.device}
          className="h-80 w-full object-cover object-top"
        />
      </button>
      <figcaption className="px-4 py-2 text-sm text-stone-500">
        {caption ? `${caption} · ` : null}
        {shot.label ?? shot.device} · {shot.viewport_width}×{shot.viewport_height}
      </figcaption>
    </figure>
  );
}

function Lightbox({
  shots,
  index,
  onClose,
  onIndex,
}: {
  shots: AuditScreenshot[];
  index: number;
  onClose: () => void;
  onIndex: (index: number) => void;
}) {
  const shot = shots[index];
  const hasPrev = index > 0;
  const hasNext = index < shots.length - 1;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowLeft" && hasPrev) onIndex(index - 1);
      if (event.key === "ArrowRight" && hasNext) onIndex(index + 1);
    };
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [hasNext, hasPrev, index, onClose, onIndex]);

  if (!shot) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/80 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={shot.label ?? shot.device}
      onClick={onClose}
    >
      <button
        type="button"
        className="absolute top-4 right-4 rounded-lg bg-white/90 px-3 py-1.5 text-sm font-medium text-stone-900"
        onClick={onClose}
      >
        Chiudi
      </button>
      {hasPrev ? (
        <button
          type="button"
          className="absolute top-1/2 left-4 -translate-y-1/2 rounded-lg bg-white/90 px-3 py-2 text-sm font-medium text-stone-900"
          onClick={(event) => {
            event.stopPropagation();
            onIndex(index - 1);
          }}
        >
          ←
        </button>
      ) : null}
      {hasNext ? (
        <button
          type="button"
          className="absolute right-4 top-1/2 -translate-y-1/2 rounded-lg bg-white/90 px-3 py-2 text-sm font-medium text-stone-900"
          onClick={(event) => {
            event.stopPropagation();
            onIndex(index + 1);
          }}
        >
          →
        </button>
      ) : null}
      <figure className="max-h-full max-w-full" onClick={(event) => event.stopPropagation()}>
        <img
          src={screenshotSrc(shot.url)}
          alt={shot.label ?? shot.device}
          className="max-h-[85vh] max-w-[min(96vw,1200px)] rounded-lg object-contain"
        />
        <figcaption className="mt-3 text-center text-sm text-stone-100">
          {shot.label ?? shot.device} · {shot.viewport_width}×{shot.viewport_height}
          <span className="text-stone-400"> · Esc per chiudere</span>
        </figcaption>
      </figure>
    </div>,
    document.body,
  );
}
