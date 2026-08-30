import { ApiError, getApiBaseUrl } from "./health";

export type Intelligence = {
  company_id: string | null;
  audit_id: string | null;
  signals: {
    technologies: string[];
    analytics: string[];
    social: { network: string; url: string }[];
    app_links?: { store: string; url: string }[];
    generator: string | null;
    aging: string[];
    osm_stars: string | null;
    has_phone: boolean;
    has_email: boolean;
    has_website: boolean;
  };
  history: {
    previous_audit_id: string;
    previous_completed_at: string | null;
    website_score_delta: number | null;
    opportunity_score_delta: number | null;
    new_finding_codes: string[];
    resolved_finding_codes: string[];
  } | null;
  monitoring: {
    last_completed_at: string | null;
    days_since: number | null;
    stale: boolean;
  };
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

export async function fetchAuditIntelligence(auditId: string): Promise<Intelligence | null> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/audits/${auditId}/intelligence`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  if (response.status === 404) return null;
  return parseJson<Intelligence>(response);
}

export async function fetchCompanyIntelligence(companyId: string): Promise<Intelligence | null> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/companies/${companyId}/intelligence`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  if (response.status === 404) return null;
  return parseJson<Intelligence>(response);
}
