function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function openExternal(url: string): void {
  if (isTauri()) {
    void import("@tauri-apps/plugin-opener")
      .then(({ openUrl }) => openUrl(url))
      .catch((err) => {
        console.error("openUrl fallito, provo window.open come ripiego:", err);
        window.open(url, "_blank", "noopener,noreferrer");
      });
    return;
  }
  // Nel browser (npm run dev) window.open deve restare sincrono nel click handler,
  // altrimenti i browser lo trattano come popup non richiesto e lo bloccano in silenzio.
  window.open(url, "_blank", "noopener,noreferrer");
}
