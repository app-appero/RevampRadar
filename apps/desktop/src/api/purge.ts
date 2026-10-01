import { ApiError, getApiBaseUrl } from "./health";

async function del(path: string): Promise<number> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, { method: "DELETE" });
  } catch {
    throw new ApiError("Impossibile raggiungere il backend.");
  }
  if (response.ok) {
    if (response.status === 204) return 1;
    const body = (await response.json().catch(() => ({}))) as { deleted?: number };
    return body.deleted ?? 0;
  }
  const payload = (await response.json().catch(() => ({}))) as { detail?: string };
  throw new ApiError(
    typeof payload.detail === "string" ? payload.detail : `Errore ${response.status}`,
    response.status,
  );
}

export const deleteAudit = (id: string) => del(`/audits/${id}`);
export const deleteAllAudits = () => del("/audits?confirm=true");
export const deleteDiscovery = (id: string) => del(`/discoveries/${id}`);
export const deleteAllDiscoveries = () => del("/discoveries?confirm=true");
export const deleteCompany = (id: string) => del(`/companies/${id}`);
export const deleteAllCompanies = () => del("/companies?confirm=true");
