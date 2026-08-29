import { Route, Routes } from "react-router-dom";

import { AuditPage } from "./pages/AuditPage";
import { CompanyPage } from "./pages/CompanyPage";
import { DiscoveryPage } from "./pages/DiscoveryPage";
import { CompaniesPage, DiscoveryRunPage } from "./pages/DiscoveryRunPage";
import { HomePage } from "./pages/HomePage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/audits/:auditId" element={<AuditPage />} />
      <Route path="/discovery" element={<DiscoveryPage />} />
      <Route path="/discoveries/:runId" element={<DiscoveryRunPage />} />
      <Route path="/companies" element={<CompaniesPage />} />
      <Route path="/companies/:companyId" element={<CompanyPage />} />
    </Routes>
  );
}
