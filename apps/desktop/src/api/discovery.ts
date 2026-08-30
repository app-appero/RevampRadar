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

export type BulkScanProgress = {
  total: number;
  pending: number;
  running: number;
  completed: number;
  failed: number;
  skipped: number;
};

export type BulkScanItem = {
  id: string;
  company_id: string;
  company_name: string;
  city: string | null;
  domain: string | null;
  status: string;
  attempts: number;
  last_error: string | null;
  audit_id: string | null;
  website_score: number | null;
  opportunity_score: number | null;
  priority: string | null;
  recommended_service: string | null;
};

export type BulkScan = {
  id: string;
  discovery_run_id: string;
  status: string;
  max_attempts: number;
  concurrency: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  progress: BulkScanProgress;
  items: BulkScanItem[];
};

export async function startBulkScan(discoveryId: string): Promise<BulkScan> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/discoveries/${discoveryId}/scans`, {
      method: "POST",
    });
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<BulkScan>(response);
}

export async function fetchBulkScan(id: string): Promise<BulkScan> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/bulk-scans/${id}`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<BulkScan>(response);
}

export async function retryFailedScan(id: string): Promise<BulkScan> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/bulk-scans/${id}/retry-failed`, {
      method: "POST",
    });
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<BulkScan>(response);
}

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
  latest_scan_id: string | null;
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
