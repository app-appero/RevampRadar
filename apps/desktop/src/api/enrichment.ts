import { ApiError, getApiBaseUrl } from "./health";

export type EnrichKind = "city" | "places" | "analysis";

export type EnrichCandidates = {
  missing_city: number;
  missing_website: number;
};

export type EnrichJob = {
  id: string;
  kind: EnrichKind;
  status: "running" | "cancelling" | "cancelled" | "completed" | "failed";
  total: number;
  processed: number;
  updated: number;
  not_found: number;
  failed: number;
  last_error: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, init);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  let payload: T | { detail?: string };
  try {
    payload = (await response.json()) as T;
  } catch {
    throw new ApiError("Risposta del backend non valida.", response.status);
  }
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload && typeof payload.detail === "string"
        ? payload.detail
        : `Errore ${response.status}`;
    throw new ApiError(detail, response.status);
  }
  return payload as T;
}

export function fetchEnrichCandidates(): Promise<EnrichCandidates> {
  return request("/enrichment/candidates");
}

// Un endpoint dedicato impedisce ai vecchi backend di ignorare company_ids
// e avviare accidentalmente un recupero globale.
const localJobs = new Map<string, EnrichJob>();

export async function startEnrichment(kind: EnrichKind, companyIds?: string[]): Promise<EnrichJob> {
  if (companyIds !== undefined) {
    const ids = [...new Set(companyIds)];
    if (!ids.length) throw new ApiError("Seleziona almeno un'azienda.");
    try {
      return await request(`/enrichment/selected/${kind}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company_ids: ids }),
      });
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 404) throw error;
    }
    if (kind === "city") throw new ApiError("Aggiorna il backend per il recupero selezionato delle citta.");
    const job: EnrichJob = {
      id: `local-${crypto.randomUUID()}`, kind, status: "running", total: ids.length,
      processed: 0, updated: 0, not_found: 0, failed: 0, last_error: null,
    };
    localJobs.set(job.id, job);
    void runSelected(job, ids);
    return { ...job };
  }
  return request(`/enrichment/${kind}`, { method: "POST" });
}

async function runSelected(job: EnrichJob, ids: string[]): Promise<void> {
  let consecutiveErrors = 0;
  for (const id of ids) {
    if (job.status !== "running") break;
    try {
      if (job.kind === "places") {
        await request(`/companies/${id}/places-enrich`, { method: "POST" });
      } else {
        const company = await request<{ website_url: string | null }>(`/companies/${id}`);
        if (!company.website_url) throw new ApiError("Azienda senza sito.", 404);
        // Una cancellazione durante la lettura non deve avviare un nuovo audit.
        if (job.status !== "running") break;
        let audit = await request<{ id: string; status: string; error_message?: string }>("/audits", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: company.website_url, company_id: id }),
        });
        while (["queued", "running"].includes(audit.status)) {
          await new Promise((resolve) => setTimeout(resolve, 1000));
          audit = await request(`/audits/${audit.id}`);
        }
        if (audit.status !== "completed") throw new ApiError(audit.error_message ?? "Analisi fallita.");
      }
      job.updated++;
      consecutiveErrors = 0;
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        job.not_found++;
        consecutiveErrors = 0;
      } else {
        job.failed++;
        job.last_error = error instanceof Error ? error.message : "Operazione fallita.";
        consecutiveErrors++;
        if (consecutiveErrors >= 3 || (error instanceof ApiError && [401, 403, 422].includes(error.status ?? 0))) {
          job.status = "failed";
        }
      }
    }
    job.processed++;
    if (job.status === "failed") return;
  }
  job.status = job.status === "cancelling" ? "cancelled" : "completed";
}

export async function fetchEnrichJob(id: string): Promise<EnrichJob> {
  const local = localJobs.get(id);
  return local ? { ...local } : request(`/enrichment/jobs/${id}`);
}

export async function cancelEnrichment(id: string): Promise<EnrichJob> {
  const local = localJobs.get(id);
  if (local) {
    if (local.status === "running") local.status = "cancelling";
    return { ...local };
  }
  return request(`/enrichment/jobs/${id}/cancel`, { method: "POST" });
}
