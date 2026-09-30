import { ApiError, getApiBaseUrl } from "./health";

export type ProfileLink = {
  label: string;
  url: string;
};

export type SenderProfile = {
  display_name: string;
  intro: string;
  website_url: string;
  freelancer_links: ProfileLink[];
  social_links: ProfileLink[];
  other_links: ProfileLink[];
  reference_location: string | null;
  reference_latitude: number | null;
  reference_longitude: number | null;
  local_radius_km: number | null;
  local_mention_enabled: boolean;
  local_mention_text: string | null;
  updated_at: string;
};

export type EmailTemplates = {
  refactor_body: string | null;
  greenfield_body: string | null;
  refactor_default: string;
  greenfield_default: string;
  refactor_tokens: string[];
  greenfield_tokens: string[];
  updated_at: string;
};

export type AiSettings = {
  provider: string;
  anthropic_api_key: string | null;
  openai_api_key: string | null;
  openapi_company_token: string | null;
  ai_available: boolean;
  openapi_available: boolean;
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

export async function fetchSenderProfile(): Promise<SenderProfile> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/settings/profile`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<SenderProfile>(response);
}

export async function saveSenderProfile(
  payload: Omit<SenderProfile, "updated_at" | "reference_latitude" | "reference_longitude">,
): Promise<SenderProfile> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/settings/profile`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<SenderProfile>(response);
}

export async function fetchEmailTemplates(): Promise<EmailTemplates> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/settings/email-templates`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<EmailTemplates>(response);
}

export async function saveEmailTemplates(payload: {
  refactor_body: string | null;
  greenfield_body: string | null;
}): Promise<EmailTemplates> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/settings/email-templates`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<EmailTemplates>(response);
}

export async function fetchAiSettings(): Promise<AiSettings> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/settings/ai`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<AiSettings>(response);
}

export async function saveAiSettings(payload: {
  provider?: string;
  anthropic_api_key?: string | null;
  openai_api_key?: string | null;
  openapi_company_token?: string | null;
}): Promise<AiSettings> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/settings/ai`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseJson<AiSettings>(response);
}
