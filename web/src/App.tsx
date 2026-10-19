import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import CaseDetailPage from "./pages/CaseDetailPage";
import LoginPage from "./pages/LoginPage";
import QueuePage from "./pages/QueuePage";
import ReportPage from "./pages/ReportPage";
import TaxonomyPage from "./pages/TaxonomyPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppShell />}>
        <Route path="/queue" element={<QueuePage />} />
        <Route path="/cases/:caseId" element={<CaseDetailPage />} />
        <Route path="/reports/:reportId" element={<ReportPage />} />
        <Route path="/taxonomy" element={<TaxonomyPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/queue" replace />} />
    </Routes>
  );
}
