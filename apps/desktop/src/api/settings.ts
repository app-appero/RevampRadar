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
  updated_at: string;
};

async function parseProfile(response: Response): Promise<SenderProfile> {
  let payload: SenderProfile | { detail?: string };
  try {
    payload = (await response.json()) as SenderProfile;
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
  return payload as SenderProfile;
}

export async function fetchSenderProfile(): Promise<SenderProfile> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/settings/profile`);
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  return parseProfile(response);
}

export async function saveSenderProfile(
  payload: Omit<SenderProfile, "updated_at">,
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
  return parseProfile(response);
}
