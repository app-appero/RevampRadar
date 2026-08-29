const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type HealthStatus = "ok" | "degraded";
export type DatabaseStatus = "ok" | "unavailable";

export type HealthResponse = {
  status: HealthStatus;
  service: string;
  version: string;
  environment: string;
  database: DatabaseStatus;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function fetchHealth(): Promise<HealthResponse> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/health`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }

  let payload: HealthResponse;
  try {
    payload = (await response.json()) as HealthResponse;
  } catch {
    throw new ApiError("Risposta del backend non valida.", response.status);
  }

  if (!response.ok && response.status !== 503) {
    throw new ApiError(`Health check fallito (${response.status}).`, response.status);
  }

  return payload;
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}
