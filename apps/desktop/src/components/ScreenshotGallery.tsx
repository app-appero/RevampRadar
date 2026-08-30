import { screenshotSrc, type AuditScreenshot } from "../api/audits";

export function ScreenshotGallery({ shots }: { shots: AuditScreenshot[] }) {
  const current = shots.filter((shot) => !isPreview(shot));
  const preview = shots.find((shot) => isPreview(shot));
  const today = current.find((shot) => shot.device === "desktop_hero" || shot.device === "desktop");

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-lg font-medium">Screenshot</h2>
        <p className="text-sm text-stone-500">
          Scorri in orizzontale: inizio pagina, contenuto e footer, desktop e mobile.
        </p>
      </div>
      {current.length > 0 ? (
        <div className="flex gap-4 overflow-x-auto pb-2">
          {current.map((shot) => (
            <ShotCard key={shot.id} shot={shot} />
          ))}
        </div>
      ) : null}

      {preview && today ? (
        <div className="space-y-3">
          <div>
            <h3 className="text-sm font-medium">Come potrebbe migliorare</h3>
            <p className="text-sm text-stone-500">
              Anteprima indicativa: testo più leggibile, CTA visibile, banner cookie nascosti.
              Non è il restyling finale né un mockup grafico.
            </p>
          </div>
          <div className="flex gap-4 overflow-x-auto pb-2">
            <ShotCard shot={today} caption="Oggi" />
            <ShotCard shot={preview} caption="Dopo (indicativo)" />
          </div>
        </div>
      ) : null}
    </section>
  );
}

function isPreview(shot: AuditScreenshot): boolean {
  return shot.preview ?? shot.device.startsWith("preview_");
}

function ShotCard({ shot, caption }: { shot: AuditScreenshot; caption?: string }) {
  return (
    <figure className="w-72 shrink-0 overflow-hidden rounded-2xl border border-stone-200 bg-white">
      <a href={screenshotSrc(shot.url)} target="_blank" rel="noreferrer">
        <img
          src={screenshotSrc(shot.url)}
          alt={caption ?? shot.label ?? shot.device}
          className="h-80 w-full object-cover object-top"
        />
      </a>
      <figcaption className="px-4 py-2 text-sm text-stone-500">
        {caption ? `${caption} · ` : null}
        {shot.label ?? shot.device} · {shot.viewport_width}×{shot.viewport_height}
      </figcaption>
    </figure>
  );
}
