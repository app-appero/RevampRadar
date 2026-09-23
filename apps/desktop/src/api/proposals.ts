import { ApiError, getApiBaseUrl } from "./health";

export type ProposalProblem = {
  code: string;
  severity: string;
  title: string;
  recommendation: string;
};

export type Proposal = {
  id: string;
  audit_id: string | null;
  company_id: string | null;
  kind: string;
  source: string;
  prompt_version: string;
  summary: string;
  priority_problems: ProposalProblem[];
  recommended_service: string;
  strategy: string;
  email_subject: string;
  email_body: string;
  brief: string;
  range_min: number;
  range_max: number;
  currency: string;
  range_note: string;
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

function aiQueryString(useAi?: boolean): string {
  return useAi == null ? "" : `?use_ai=${useAi ? "true" : "false"}`;
}

export function generateProposal(auditId: string, useAi?: boolean): Promise<Proposal> {
  return request(`/audits/${auditId}/proposal${aiQueryString(useAi)}`, { method: "POST" });
}

export function generateGreenfieldProposal(companyId: string, useAi?: boolean): Promise<Proposal> {
  return request(`/companies/${companyId}/greenfield-proposal${aiQueryString(useAi)}`, { method: "POST" });
}

export async function fetchAuditProposal(auditId: string): Promise<Proposal | null> {
  try {
    return await request<Proposal>(`/audits/${auditId}/proposal`);
  } catch (err: unknown) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function fetchCompanyProposal(companyId: string): Promise<Proposal | null> {
  try {
    return await request<Proposal>(`/companies/${companyId}/proposal`);
  } catch (err: unknown) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}
