import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { getApiAuthHeader, getApiBaseUrl } from "./api/apiTarget";
import App from "./App";
import "./index.css";

// Con il backend remoto (protetto da Basic Auth) aggiunge le credenziali alle sole
// richieste dirette al backend; in locale non cambia nulla.
const originalFetch = window.fetch.bind(window);
window.fetch = (input, init) => {
  const auth = getApiAuthHeader();
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  if (!auth || !url.startsWith(getApiBaseUrl())) return originalFetch(input, init);
  const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
  headers.set("Authorization", auth);
  return originalFetch(input, { ...init, headers });
};

const queryClient: QueryClient = new QueryClient({
  // Dopo qualsiasi azione che scrive (analisi, recuperi, salvataggi...) ricarica i dati
  // in uso: le altre schermate non restano ferme alla versione vecchia.
  mutationCache: new MutationCache({
    onSuccess: () => {
      void queryClient.invalidateQueries();
    },
  }),
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: true,
      // Breve: tornando su una pagina dopo qualche secondo i dati vengono riletti
      // (un'analisi finita nel frattempo compare senza dover cambiare ambiente).
      staleTime: 10 * 1000,
      gcTime: 30 * 60 * 1000,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
