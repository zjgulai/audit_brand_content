import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import CaseDetailPage from "./pages/CaseDetailPage";
import LoginPage from "./pages/LoginPage";
import QueuePage from "./pages/QueuePage";
import ReportPage from "./pages/ReportPage";
import TaxonomyPage from "./pages/TaxonomyPage";

const AdminGrantsPage = lazy(() => import("./pages/AdminGrantsPage"));
const AdminSessionsPage = lazy(() => import("./pages/AdminSessionsPage"));
const AppealsPage = lazy(() => import("./pages/AppealsPage"));
const CasesPage = lazy(() => import("./pages/CasesPage"));
const InboxPage = lazy(() => import("./pages/InboxPage"));
const ReleasePage = lazy(() => import("./pages/ReleasePage"));
const ReportsIndexPage = lazy(() => import("./pages/ReportsIndexPage"));
const SubmitPage = lazy(() => import("./pages/SubmitPage"));
const TakedownPage = lazy(() => import("./pages/TakedownPage"));

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppShell />}>
        {/* P-01 提交单 */}
        <Route
          path="/submit"
          element={
            <Suspense fallback={<p className="hint">加载提交单…</p>}>
              <SubmitPage />
            </Suspense>
          }
        />
        {/* P-02 收件箱与我的内容 */}
        <Route
          path="/inbox"
          element={
            <Suspense fallback={<p className="hint">加载收件箱…</p>}>
              <InboxPage />
            </Suspense>
          }
        />
        <Route
          path="/my-cases"
          element={
            <Suspense fallback={<p className="hint">加载我的内容…</p>}>
              <InboxPage />
            </Suspense>
          }
        />
        {/* P-05 复核队列 */}
        <Route path="/queue" element={<QueuePage />} />
        {/* P-03 案件总览 */}
        <Route
          path="/cases"
          element={
            <Suspense fallback={<p className="hint">加载案件总览…</p>}>
              <CasesPage />
            </Suspense>
          }
        />
        {/* P-04 案件详情 */}
        <Route path="/cases/:caseId" element={<CaseDetailPage />} />
        {/* P-06 申诉中心 */}
        <Route
          path="/appeals"
          element={
            <Suspense fallback={<p className="hint">加载申诉中心…</p>}>
              <AppealsPage />
            </Suspense>
          }
        />
        <Route
          path="/appeals/:appealId"
          element={
            <Suspense fallback={<p className="hint">加载申诉详情…</p>}>
              <AppealsPage />
            </Suspense>
          }
        />
        {/* P-07 签发中心 G-1 */}
        <Route
          path="/release"
          element={
            <Suspense fallback={<p className="hint">加载签发台…</p>}>
              <ReleasePage />
            </Suspense>
          }
        />
        <Route
          path="/release/:caseId"
          element={
            <Suspense fallback={<p className="hint">加载签发核验台…</p>}>
              <ReleasePage />
            </Suspense>
          }
        />
        {/* P-08 下线任务台 */}
        <Route
          path="/takedown"
          element={
            <Suspense fallback={<p className="hint">加载下线任务台…</p>}>
              <TakedownPage />
            </Suspense>
          }
        />
        {/* P-09 报告索引与详情 */}
        <Route
          path="/reports"
          element={
            <Suspense fallback={<p className="hint">加载报告索引…</p>}>
              <ReportsIndexPage />
            </Suspense>
          }
        />
        <Route path="/reports/:reportId" element={<ReportPage />} />
        {/* P-10 规则与分类规范 */}
        <Route path="/taxonomy" element={<TaxonomyPage />} />
        <Route path="/rules" element={<TaxonomyPage />} />
        {/* P-11 授权名单治理 */}
        <Route
          path="/admin/grants"
          element={
            <Suspense fallback={<p className="hint">加载授权名单治理…</p>}>
              <AdminGrantsPage />
            </Suspense>
          }
        />
        {/* P-12 会话与安全审计 */}
        <Route
          path="/admin/sessions"
          element={
            <Suspense fallback={<p className="hint">加载会话与安全审计…</p>}>
              <AdminSessionsPage />
            </Suspense>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/queue" replace />} />
    </Routes>
  );
}
