import type { QueryClient } from "@tanstack/react-query";

import { fetchAiSettings } from "../api/settings";

/**
 * Legge lo stato AI al momento del clic (mai dalla cache: la chiave può essere stata appena
 * salvata in Impostazioni). Se non riesce a leggerlo, restituisce true: mostrare la scelta è
 * innocuo, perché senza chiave il backend ripiega comunque sul testo deterministico.
 */
export async function isAiAvailableNow(queryClient: QueryClient): Promise<boolean> {
  try {
    const data = await queryClient.fetchQuery({
      queryKey: ["ai-settings"],
      queryFn: fetchAiSettings,
      staleTime: 0,
    });
    return data.ai_available;
  } catch {
    return true;
  }
}
