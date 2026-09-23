import { ApiError, getApiBaseUrl } from "./health";

export type GrowthScore = {
  id: string;
  company_id: string;
  score: number;
  priority: string;
  confidence: number;
  explanation: string;
  top_reasons: string[];
  positive_factors: string[];
  negative_factors: string[];
  recommended_service: string;
  components: Record<string, unknown> | null;
  peer_sample_size: number;
  formula_version: string;
  created_at: string;
  updated_at: string;
};

async function parseJson<T>(response: Response): Promise<T> {
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, init);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<T>(response);
}

export async function fetchCompanyGrowthScore(companyId: string): Promise<GrowthScore | null> {
  try {
    return await request<GrowthScore>(`/companies/${companyId}/growth-score`);
  } catch (err: unknown) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export function recomputeCompanyGrowthScore(companyId: string): Promise<GrowthScore> {
  return request(`/companies/${companyId}/growth-score`, { method: "POST" });
}
