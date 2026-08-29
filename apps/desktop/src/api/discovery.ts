import { ApiError, getApiBaseUrl } from "./health";

export type DiscoveryStatus = "queued" | "running" | "completed" | "partial" | "failed" | string;

export type CompanySummary = {
  id: string;
  name: string;
  category: string | null;
  city: string | null;
  region: string | null;
  country: string | null;
  website_url: string | null;
  phone: string | null;
  email: string | null;
  source: string;
  status: string;
  domain: string | null;
};

export type CompanyDetail = CompanySummary & {
  external_id: string | null;
  created_at: string;
  website_id: string | null;
};

export type DiscoveryRun = {
  id: string;
  industry: string;
  location: string;
  max_results: number;
  provider: string;
  status: DiscoveryStatus;
  total_found: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  companies: CompanySummary[];
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

export async function createDiscovery(input: {
  industry: string;
  location: string;
  max_results: number;
}): Promise<DiscoveryRun> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/discoveries`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<DiscoveryRun>(response);
}

export async function fetchDiscovery(id: string): Promise<DiscoveryRun> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/discoveries/${id}`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<DiscoveryRun>(response);
}

export async function fetchCompanies(): Promise<CompanySummary[]> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/companies`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<CompanySummary[]>(response);
}

export async function fetchCompany(id: string): Promise<CompanyDetail> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/companies/${id}`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<CompanyDetail>(response);
}
