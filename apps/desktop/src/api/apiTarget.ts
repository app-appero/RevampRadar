export type ApiMode = "local" | "remote";

const STORAGE_KEY = "revampradar.apiMode";
const LOCAL_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const REMOTE_URL: string | undefined = import.meta.env.VITE_API_REMOTE_URL;
const REMOTE_AUTH: string | undefined = import.meta.env.VITE_API_BASIC_AUTH;

export function remoteAvailable(): boolean {
  return Boolean(REMOTE_URL);
}

// Su Android non esiste un backend locale: si usa sempre quello remoto.
const IS_ANDROID = typeof navigator !== "undefined" && /Android/i.test(navigator.userAgent);

export function getApiMode(): ApiMode {
  if (IS_ANDROID && remoteAvailable()) return "remote";
  try {
    if (remoteAvailable() && localStorage.getItem(STORAGE_KEY) === "remote") return "remote";
  } catch {
    // localStorage non disponibile: resta in locale
  }
  return "local";
}

// Il cambio ricarica la pagina: le query in cache appartengono all'altro backend.
export function setApiMode(mode: ApiMode): void {
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    return;
  }
  window.location.reload();
}

export function getApiBaseUrl(): string {
  return getApiMode() === "remote" && REMOTE_URL ? REMOTE_URL.replace(/\/+$/, "") : LOCAL_URL;
}

// Credenziali Basic solo per il backend remoto (formato "utente:password").
export function getApiAuthHeader(): string | null {
  return getApiMode() === "remote" && REMOTE_AUTH ? `Basic ${btoa(REMOTE_AUTH)}` : null;
}
