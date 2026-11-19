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
  "uncontactable",
  "not_now",
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
  uncontactable: "Impossibili da contattare",
  not_now: "Al momento NON da contattare",
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
  email_sent: "Email inviata (storico)",
  dm_sent: "Primo DM inviato (storico)",
  concept_sent: "Concept inviato (storico)",
};

export type Tag = { id: string; name: string };
export type Note = { id: string; body: string; created_at: string };
export type Activity = {
  id: string;
  type: string;
  note: string | null;
  occurred_at: string | null;
  occurred_on?: string | null;
  due_at: string | null;
  completed_at: string | null;
  channel?: string | null;
  sender?: string | null;
  recipient?: string | null;
  batch_id?: string | null;
  external_ref?: string | null;
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
  places_checked_at: string | null;
  has_email: boolean;
  has_phone: boolean;
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
  instagram_handle?: string | null;
  instagram_last_post_at?: string | null;
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

export type PipelineCategory = { value: string; label: string; count: number; variants: string[] };

// Compatibilita con backend precedenti all'endpoint delle faccette.
const legacyCategoryApis = new Set<string>();
const CATEGORY_ALIASES: Record<string, string> = {
  barbieri: "barbiere", hotels: "hotel", albergo: "hotel", alberghi: "hotel",
  ristoranti: "ristorante", restaurant: "ristorante", parrucchieri: "parrucchiere",
  hairdresser: "parrucchiere", clothes: "abbigliamento",
};
function categoryKey(value: string | null): string {
  const key = (value ?? "").trim().toLocaleLowerCase("it").replace(/\s+/g, " ");
  return CATEGORY_ALIASES[key] ?? key;
}

export async function fetchOpportunityCategories(filters: OpportunityFilters): Promise<PipelineCategory[]> {
  const baseUrl = getApiBaseUrl();
  const params = opportunityParams({ ...filters, category: undefined });
  if (!legacyCategoryApis.has(baseUrl)) {
    try {
      return await request(`/opportunities/categories?${params}`);
    } catch (error) {
      if (!(error instanceof ApiError) || ![404, 422].includes(error.status ?? 0)) throw error;
      legacyCategoryApis.add(baseUrl);
    }
  }
  const rows = await request<OpportunitySummary[]>(`/opportunities?${params}`);
  const groups = new Map<string, PipelineCategory>();
  for (const row of rows) {
    const key = categoryKey(row.category);
    if (!key) continue;
    const group = groups.get(key) ?? { value: key, label: key[0].toLocaleUpperCase("it") + key.slice(1), count: 0, variants: [] };
    group.count += 1;
    if (row.category && !group.variants.includes(row.category)) group.variants.push(row.category);
    groups.set(key, group);
  }
  return [...groups.values()].sort((a, b) => a.label.localeCompare(b.label, "it"));
}

export type PipelineImportResult = {
  total: number;
  updated: number;
  unchanged: number;
  errors: { company: string; error: string }[];
};

// JSON completo delle aziende che rispettano i filtri correnti (per arricchimento esterno).
export function exportOpportunities(filters: OpportunityFilters = {}): Promise<{ total: number }> {
  return request(`/opportunities/export?${opportunityParams(filters)}`);
}

export type ManualCompanyResult = {
  outcome: "created" | "existing" | "updated" | "conflict";
  company_id: string | null;
  opportunity_id: string | null;
  status: string | null;
  error: string | null;
  warnings: string[];
  candidates: {
    company_id: string;
    opportunity_id: string | null;
    name: string;
    city: string | null;
    region: string | null;
    website_url: string | null;
    email: string | null;
    phone: string | null;
    reasons: string[];
  }[];
};

export async function createManualCompany(
  path: string,
  method: "POST",
  body: unknown,
): Promise<ManualCompanyResult> {
  if (path !== "/companies" || method !== "POST") {
    throw new ApiError("Il salvataggio di un'azienda non passa dall'analisi.");
  }
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  let payload: ManualCompanyResult | { detail?: unknown };
  try {
    payload = (await response.json()) as ManualCompanyResult | { detail?: unknown };
  } catch {
    throw new ApiError("Risposta del backend non valida.", response.status);
  }
  if (response.status === 409 && payload && typeof payload === "object" && "outcome" in payload) {
    return payload;
  }
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload && typeof payload.detail === "string"
        ? payload.detail
        : `Errore ${response.status}`;
    throw new ApiError(detail, response.status);
  }
  return payload as ManualCompanyResult;
}

export function importOpportunities(payload: unknown): Promise<PipelineImportResult> {
  return request("/opportunities/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchOpportunities(filters: OpportunityFilters = {}): Promise<OpportunitySummary[]> {
  if (filters.category) {
    // Attende il controllo di compatibilita anche al ripristino di filtri salvati.
    await fetchOpportunityCategories(filters);
    if (legacyCategoryApis.has(getApiBaseUrl())) {
      const rows = await request<OpportunitySummary[]>(`/opportunities?${opportunityParams({ ...filters, category: undefined })}`);
      return rows.filter((row) => categoryKey(row.category) === categoryKey(filters.category!));
    }
  }
  return request(`/opportunities?${opportunityParams(filters)}`);
}

function opportunityParams(filters: OpportunityFilters): string {
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
  return query;
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
