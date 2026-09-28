import { ApiError, getApiBaseUrl } from "./health";

export type PaletteColor = { role: string; hex: string };

export type DesignBrief = {
  style: string | null;
  palette: PaletteColor[] | null;
  typography: string | null;
  tone_of_voice: string | null;
  spacing: string | null;
  border_radius: string | null;
  image_treatment: string | null;
  primary_cta: string | null;
  notes: string | null;
  source: string;
  updated_at: string;
};

export type DesignBriefInput = Partial<
  Omit<DesignBrief, "source" | "updated_at" | "palette"> & { palette: PaletteColor[] }
>;

export type ConceptSummary = {
  id: string;
  version: number;
  status: string;
  is_current: boolean;
  source: string;
  generator_version: string;
  sections: string[] | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  open_url: string;
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

const JSON_HEADERS = { "Content-Type": "application/json" };

export function fetchDesignBrief(companyId: string): Promise<DesignBrief> {
  return request(`/companies/${companyId}/design-brief`);
}

export function updateDesignBrief(companyId: string, payload: DesignBriefInput): Promise<DesignBrief> {
  return request(`/companies/${companyId}/design-brief`, {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });
}

export function regenerateDesignBrief(companyId: string): Promise<DesignBrief> {
  return request(`/companies/${companyId}/design-brief/regenerate`, { method: "POST" });
}

export function fetchConcepts(companyId: string): Promise<ConceptSummary[]> {
  return request(`/companies/${companyId}/concepts`);
}

export function generateConcept(companyId: string): Promise<ConceptSummary> {
  return request(`/companies/${companyId}/concepts`, { method: "POST" });
}

export async function deleteConcept(companyId: string, conceptId: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/companies/${companyId}/concepts/${conceptId}`, {
      method: "DELETE",
    });
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  if (!response.ok) {
    let detail = `Errore ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      // ignore: nessun corpo o corpo non JSON
    }
    throw new ApiError(detail, response.status);
  }
}

export function conceptFileUrl(openUrl: string): string {
  return `${getApiBaseUrl()}${openUrl}`;
}
