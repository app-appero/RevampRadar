import { ApiError, getApiBaseUrl } from "./health";

export type AuditStatus = "queued" | "running" | "completed" | "failed";

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
  status: "skipped" | "completed" | "failed" | string;
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
  status: AuditStatus;
  request_url: string;
  normalized_url: string;
  domain: string;
  scanner_version: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
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

export async function createAudit(url: string): Promise<Audit> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/audits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
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

export function screenshotSrc(path: string): string {
  return `${getApiBaseUrl()}${path}`;
}
