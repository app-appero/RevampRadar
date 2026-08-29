import { Route, Routes } from "react-router-dom";

import { AuditPage } from "./pages/AuditPage";
import { HomePage } from "./pages/HomePage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/audits/:auditId" element={<AuditPage />} />
    </Routes>
  );
}
