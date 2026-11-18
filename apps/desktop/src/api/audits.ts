import { ApiError, getApiBaseUrl } from "./health";

export type AuditStatus = "queued" | "running" | "completed" | "failed";

export type CompanyAuditHistoryItem = {
  id: string;
  created_at: string;
  status: string;
  website_score: number | null;
  technical_score: number | null;
  performance_score: number | null;
  ui_score: number | null;
  ux_score: number | null;
  mobile_score: number | null;
  conversion_score: number | null;
  seo_score: number | null;
  trust_score: number | null;
  business_score: number | null;
  opportunity_score: number | null;
  priority: string | null;
};

export type AuditFinding = {
  id: string;
  category: string;
  severity: "info" | "low" | "medium" | "high" | "critical" | string;
  code: string;
  title: string;
  description: string;
  evidence: string | null;
  recommendation: string;
  source_type: string;
};

export type AuditScreenshot = {
  id: string;
  device: string;
  viewport_width: number;
  viewport_height: number;
  url: string;
  label?: string;
  preview?: boolean;
};

export type WebsiteScore = {
  overall_score: number;
  technical_score: number;
  performance_score: number;
  ui_score: number | null;
  ux_score: number;
  mobile_score: number;
  conversion_score: number;
  seo_score: number;
  trust_score: number;
  explanation: string;
  components: Record<string, unknown> | null;
  formula_version: string;
};

export type OpportunityScore = {
  website_score: number;
  business_score: number;
  opportunity_score: number;
  confidence: number;
  priority: "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH" | string;
  explanation: string;
  top_reasons: string[];
  positive_factors: string[];
  negative_factors: string[];
  recommended_service: string;
  components: Record<string, unknown> | null;
  formula_version: string;
};

export type AIAnalysis = {
  status: "skipped" | "skipped_free_mode" | "completed" | "failed" | string;
  prompt_version: string | null;
  provider: string | null;
  model: string | null;
  reason: string | null;
  error: string | null;
  ui_score: number | null;
  ux_score: number | null;
  confidence: number | null;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  notes: string | null;
};

export type Audit = {
  id: string;
  company_id: string | null;
  status: AuditStatus;
  free_only?: boolean;
  ai_status?: string;
  request_url: string;
  normalized_url: string;
  domain: string;
  scanner_version: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  progress_percent: number;
  progress_label: string | null;
  http: Record<string, unknown> | null;
  html: Record<string, unknown> | null;
  seo: Record<string, unknown> | null;
  performance: Record<string, unknown> | null;
  findings: AuditFinding[];
  screenshots: AuditScreenshot[];
  website_score: WebsiteScore | null;
  opportunity_score: OpportunityScore | null;
  ai_analysis: AIAnalysis | null;
};

async function parseAudit(response: Response): Promise<Audit> {
  let payload: Audit | { detail?: string };
  try {
    payload = (await response.json()) as Audit;
  } catch {
    throw new ApiError("Risposta del backend non valida.", response.status);
  }
  if (!response.ok) {
    const detail =
      "detail" in payload && typeof payload.detail === "string"
        ? payload.detail
        : `Errore ${response.status}`;
    throw new ApiError(detail, response.status);
  }
  return payload as Audit;
}

export type AuditSummary = {
  id: string;
  status: AuditStatus;
  domain: string;
  normalized_url: string;
  created_at: string;
  completed_at: string | null;
  progress_percent?: number;
  progress_label?: string | null;
  website_score: number | null;
  opportunity_score: number | null;
  priority: string | null;
};

export async function fetchRecentAudits(limit = 12): Promise<AuditSummary[]> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/audits?limit=${limit}`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  if (!response.ok) {
    throw new ApiError(`Errore ${response.status}`, response.status);
  }
  return (await response.json()) as AuditSummary[];
}

// L'API usa free_only=true di default (chiamate automatiche). Un'analisi lanciata a mano
// dal desktop resta completa (AI + PageSpeed se le chiavi ci sono), salvo freeOnly esplicito.
export async function createAudit(url: string, companyId?: string, freeOnly = false): Promise<Audit> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/audits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, company_id: companyId ?? null, free_only: freeOnly }),
    });
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseAudit(response);
}

export async function fetchAudit(id: string): Promise<Audit> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/audits/${id}`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseAudit(response);
}

export async function fetchCompanyAuditHistory(companyId: string): Promise<CompanyAuditHistoryItem[]> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/audits/companies/${companyId}`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  if (!response.ok) {
    throw new ApiError(`Errore ${response.status}`, response.status);
  }
  return (await response.json()) as CompanyAuditHistoryItem[];
}

export function screenshotSrc(path: string): string {
  return `${getApiBaseUrl()}${path}`;
}
