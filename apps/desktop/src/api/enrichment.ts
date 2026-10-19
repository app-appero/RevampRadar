import { ApiError, getApiBaseUrl } from "./health";

export type EnrichKind = "city" | "places" | "analysis";

export type EnrichCandidates = {
  missing_city: number;
  missing_website: number;
};

export type EnrichJob = {
  id: string;
  kind: EnrichKind;
  status: "running" | "completed" | "failed";
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

export function startEnrichment(kind: EnrichKind, companyIds?: string[]): Promise<EnrichJob> {
  return request(`/enrichment/${kind}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: companyIds === undefined ? undefined : JSON.stringify({ company_ids: companyIds }) });
}

export function fetchEnrichJob(id: string): Promise<EnrichJob> {
  return request(`/enrichment/jobs/${id}`);
}
