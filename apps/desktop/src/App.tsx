import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AuditPage } from "./pages/AuditPage";
import { CompanyPage } from "./pages/CompanyPage";
import { DiscoveryPage } from "./pages/DiscoveryPage";
import { CompaniesPage, DiscoveryRunPage } from "./pages/DiscoveryRunPage";
import { HomePage } from "./pages/HomePage";
import { MapPage } from "./pages/MapPage";
import { PipelinePage } from "./pages/PipelinePage";
import { AgendaPage } from "./pages/AgendaPage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/audits/:auditId" element={<AuditPage />} />
        <Route path="/discovery" element={<DiscoveryPage />} />
        <Route path="/discoveries/:runId" element={<DiscoveryRunPage />} />
        <Route path="/pipeline" element={<PipelinePage />} />
        <Route path="/agenda" element={<AgendaPage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/companies" element={<CompaniesPage />} />
        <Route path="/companies/:companyId" element={<CompanyPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
