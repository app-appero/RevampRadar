import { ApiError, getApiBaseUrl } from "./health";

export type MapPoint = {
  company_id: string;
  name: string;
  city: string | null;
  category: string | null;
  latitude: number;
  longitude: number;
  opportunity_score: number | null;
  website_score: number | null;
  priority: string | null;
  has_app: boolean;
  has_website: boolean;
  is_contactable: boolean;
  cluster_id: number;
  audit_id: string | null;
};

export type MapCluster = {
  id: number;
  size: number;
  label: string;
  centroid_lat: number;
  centroid_lon: number;
  avg_opportunity_score: number | null;
  high_share: number;
  app_share: number;
  no_site_share: number;
  top_city: string | null;
  top_category: string | null;
};

export type MapPayload = {
  points: MapPoint[];
  clusters: MapCluster[];
  mapped_count: number;
  unmapped_count: number;
  generated_at: string;
};

export type BackfillResult = {
  updated: number;
  skipped: number;
  remaining: number;
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

export async function fetchMap(): Promise<MapPayload> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/map`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<MapPayload>(response);
}

export async function backfillMapCoords(): Promise<BackfillResult> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/map/backfill`, { method: "POST" });
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<BackfillResult>(response);
}
