import { ApiError, getApiBaseUrl } from "./health";

export const CRM_STATUSES = [
  "discovered",
  "analyzed",
  "qualified",
  "shortlisted",
  "to_contact",
  "contacted",
  "replied",
  "meeting",
  "proposal",
  "won",
  "lost",
] as const;

export const CRM_STATUS_LABELS: Record<string, string> = {
  discovered: "Scoperta",
  analyzed: "Analizzata",
  qualified: "Qualificata",
  shortlisted: "Shortlist",
  to_contact: "Da contattare",
  contacted: "Contattata",
  replied: "Risposta",
  meeting: "Meeting",
  proposal: "Proposta",
  won: "Vinta",
  lost: "Persa",
};

export const ACTIVITY_TYPES = ["call", "email", "meeting", "note", "other"] as const;

export const SCHEDULED_ACTIVITY_TYPES = ["call", "email", "meeting", "other"] as const;

export const ACTIVITY_LABELS: Record<string, string> = {
  call: "Chiamata",
  email: "Email",
  meeting: "Meeting",
  note: "Nota",
  other: "Altro",
  status_change: "Cambio stato",
};

export type Tag = { id: string; name: string };
export type Note = { id: string; body: string; created_at: string };
export type Activity = {
  id: string;
  type: string;
  note: string | null;
  occurred_at: string | null;
  due_at: string | null;
  completed_at: string | null;
  created_at: string;
};

export type AgendaHistoryItem = {
  id: string;
  opportunity_id: string;
  company_id: string;
  company_name: string;
  type: string;
  note: string | null;
  due_at: string;
  completed_at: string;
  created_at: string;
};

export type AgendaItem = {
  id: string;
  opportunity_id: string;
  company_id: string;
  company_name: string;
  type: string;
  note: string | null;
  due_at: string;
  created_at: string;
  is_overdue: boolean;
};

export type OpportunitySummary = {
  id: string;
  company_id: string;
  company_name: string;
  category: string | null;
  city: string | null;
  region: string | null;
  website_url: string | null;
  domain: string | null;
  status: string;
  is_favorite: boolean;
  tags: Tag[];
  website_score: number | null;
  opportunity_score: number | null;
  priority: string | null;
  latest_audit_id: string | null;
  has_website: boolean;
  growth_score: number | null;
  growth_priority: string | null;
  segment: "refactor" | "greenfield";
  updated_at: string;
};

export type OpportunityDetail = OpportunitySummary & {
  notes: Note[];
  activities: Activity[];
};

export type Dashboard = {
  total: number;
  favorites: number;
  shortlisted: number;
  high_priority: number;
  to_contact: number;
  counts: Record<string, number>;
};

export type OpportunityFilters = {
  status?: string;
  favorite?: boolean;
  shortlist?: boolean;
  q?: string;
  category?: string;
  city?: string;
  tag?: string;
  min_score?: number;
  priority?: string;
  segment?: "refactor" | "greenfield";
  contactable?: boolean;
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

export function fetchDashboard(): Promise<Dashboard> {
  return request("/opportunities/dashboard");
}

export function fetchOpportunities(filters: OpportunityFilters = {}): Promise<OpportunitySummary[]> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.favorite) params.set("favorite", "true");
  if (filters.shortlist) params.set("shortlist", "true");
  if (filters.q) params.set("q", filters.q);
  if (filters.category) params.set("category", filters.category);
  if (filters.city) params.set("city", filters.city);
  if (filters.tag) params.set("tag", filters.tag);
  if (filters.min_score != null) params.set("min_score", String(filters.min_score));
  if (filters.priority) params.set("priority", filters.priority);
  if (filters.segment) params.set("segment", filters.segment);
  if (filters.contactable) params.set("contactable", "true");
  const query = params.toString();
  return request(`/opportunities${query ? `?${query}` : ""}`);
}

export function fetchCompanyOpportunity(companyId: string): Promise<OpportunityDetail> {
  return request(`/companies/${companyId}/opportunity`);
}

export function updateOpportunity(
  id: string,
  payload: { status?: string; is_favorite?: boolean },
): Promise<OpportunityDetail> {
  return request(`/opportunities/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function addNote(id: string, body: string): Promise<OpportunityDetail> {
  return request(`/opportunities/${id}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
}

export function addTag(id: string, name: string): Promise<OpportunityDetail> {
  return request(`/opportunities/${id}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export function removeTag(id: string, tagId: string): Promise<OpportunityDetail> {
  return request(`/opportunities/${id}/tags/${tagId}`, { method: "DELETE" });
}

export function addActivity(
  id: string,
  payload: { type: string; note?: string; due_at?: string; occurred_at?: string },
): Promise<OpportunityDetail> {
  return request(`/opportunities/${id}/activities`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchAgenda(params: {
  from?: string;
  to?: string;
  include_overdue?: boolean;
}): Promise<AgendaItem[]> {
  const search = new URLSearchParams();
  if (params.from) search.set("from", params.from);
  if (params.to) search.set("to", params.to);
  if (params.include_overdue === false) search.set("include_overdue", "false");
  const query = search.toString();
  return request(`/agenda${query ? `?${query}` : ""}`);
}

export function fetchAgendaHistory(params: {
  from?: string;
  to?: string;
  limit?: number;
}): Promise<AgendaHistoryItem[]> {
  const search = new URLSearchParams();
  if (params.from) search.set("from", params.from);
  if (params.to) search.set("to", params.to);
  if (params.limit != null) search.set("limit", String(params.limit));
  const query = search.toString();
  return request(`/agenda/history${query ? `?${query}` : ""}`);
}

export function completeActivity(activityId: string): Promise<Activity> {
  return request(`/activities/${activityId}/complete`, { method: "POST" });
}

export function reopenActivity(activityId: string): Promise<Activity> {
  return request(`/activities/${activityId}/reopen`, { method: "POST" });
}

export async function deleteActivity(activityId: string): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/activities/${activityId}`, { method: "DELETE" });
  if (!response.ok) {
    let detail = `Errore ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, response.status);
  }
}
