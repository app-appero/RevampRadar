import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AuditPage } from "./pages/AuditPage";
import { CompanyPage } from "./pages/CompanyPage";
import { DiscoveryPage } from "./pages/DiscoveryPage";
import { CompaniesPage, DiscoveryRunPage } from "./pages/DiscoveryRunPage";
import { HomePage } from "./pages/HomePage";
import { PipelinePage } from "./pages/PipelinePage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/audits/:auditId" element={<AuditPage />} />
        <Route path="/discovery" element={<DiscoveryPage />} />
        <Route path="/discoveries/:runId" element={<DiscoveryRunPage />} />
        <Route path="/pipeline" element={<PipelinePage />} />
        <Route path="/companies" element={<CompaniesPage />} />
        <Route path="/companies/:companyId" element={<CompanyPage />} />
      </Route>
    </Routes>
  );
}
