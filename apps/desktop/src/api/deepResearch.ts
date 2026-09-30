import { ApiError, getApiBaseUrl } from "./health";

export type ResearchStatus = "never" | "in_progress" | "completed" | "partial" | "failed" | "stale";

export type DigitalPresenceChannel = { found: boolean; url: string | null; source: string | null };

export type CompanyBrief = {
  version: string;
  generated_at: string;
  company: { name: string; category: string | null; city: string | null };
  what_it_does: string | null;
  what_it_does_source: string;
  value_elements: { label: string; evidence: string; source: string }[];
  digital_presence: {
    channels: Record<string, DigitalPresenceChannel>;
    other: { network: string; url: string; source: string }[];
  };
  business_signals: {
    revenue_available: boolean;
    revenue_latest: BusinessSignalValue | null;
    revenue_history: BusinessSignalValue[];
    revenue_trend: BusinessSignalValue | null;
    employees: BusinessSignalValue | null;
    founding_year: BusinessSignalValue | null;
    legal_form: BusinessSignalValue | null;
  };
  website_problems: string[];
  homepage_direction: string | null;
  homepage_direction_source: string;
  missing_information: string[];
  pages_researched: { kind: string; url: string; title: string | null }[];
};

export type BusinessSignalValue = {
  value: string;
  unit: string | null;
  period: string | null;
  source: string;
  confidence: string;
  is_manual: boolean;
};

export type CompanyResearch = {
  company_id: string;
  status: ResearchStatus;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  progress_percent: number;
  progress_label: string | null;
  website_findings: Record<string, unknown> | null;
  digital_presence: CompanyBrief["digital_presence"] | null;
  social_signals: Record<string, unknown> | null;
  external_sources: unknown[] | null;
  brief: CompanyBrief | null;
  research_version: string;
  updated_at: string;
};

export type BusinessSignal = {
  id: string;
  key: string;
  period: string;
  label: string;
  value: string;
  unit: string | null;
  source: string;
  source_url: string | null;
  observed_at: string | null;
  confidence: string;
  is_manual: boolean;
  created_at: string;
  updated_at: string;
};

export type BusinessSignalInput = {
  key: string;
  period?: string;
  label: string;
  value: string;
  unit?: string | null;
  source: string;
  source_url?: string | null;
  observed_at?: string | null;
  confidence?: "verified" | "estimated" | "manual" | "unverified";
};

export const RESEARCH_STATUS_LABELS: Record<ResearchStatus, string> = {
  never: "Mai approfondita",
  in_progress: "Ricerca in corso",
  completed: "Completata",
  partial: "Parziale",
  failed: "Fallita",
  stale: "Da aggiornare",
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

export function fetchCompanyResearch(companyId: string): Promise<CompanyResearch> {
  return request(`/companies/${companyId}/research`);
}

export function startCompanyResearch(companyId: string): Promise<CompanyResearch> {
  return request(`/companies/${companyId}/research`, { method: "POST" });
}

export function fetchBusinessSignals(companyId: string): Promise<BusinessSignal[]> {
  return request(`/companies/${companyId}/business-signals`);
}

export function enrichFromRegistry(companyId: string, vat?: string): Promise<BusinessSignal[]> {
  return request(`/companies/${companyId}/registry-enrichment`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(vat ? { vat } : {}),
  });
}

export function saveBusinessSignal(companyId: string, payload: BusinessSignalInput): Promise<BusinessSignal> {
  return request(`/companies/${companyId}/business-signals`, {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });
}

export async function deleteBusinessSignal(companyId: string, signalId: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/companies/${companyId}/business-signals/${signalId}`, {
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
