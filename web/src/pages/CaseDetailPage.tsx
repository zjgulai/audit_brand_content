import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { reviewApi, type CaseDetail, type ReportSummary } from "../api/client";

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    let alive = true;
    Promise.all([reviewApi.getCase(caseId), reviewApi.listReports()])
      .then(([caseDetail, reportRows]) => {
        if (!alive) return;
        setDetail(caseDetail);
        setReports(reportRows.filter((r) => r.case_id === caseId));
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
  }, [caseId]);

  if (error) return <p className="error">读取失败：{error}</p>;
  if (!detail) return <p>加载中…</p>;

  const ir = detail.ir;
  const decision = ir.decision;
  const coverage = ir.coverage;

  return (
    <section>
      <h1>案件详情</h1>
      <p>
        案件：<code>{detail.case_id}</code>
      </p>

      <h2>判定</h2>
      <table>
        <tbody>
          <tr><th>状态</th><td>{decision.state}</td></tr>
          <tr><th>层</th><td>{decision.layer}</td></tr>
          <tr><th>放行状态</th><td>{decision.release_status}</td></tr>
          <tr><th>并行义务</th><td>{(decision.obligations ?? []).join("、") || "无"}</td></tr>
        </tbody>
      </table>

      <h2>覆盖证明</h2>
      <table>
        <tbody>
          <tr><th>coverage_state</th><td>{coverage.coverage_state}</td></tr>
          <tr><th>评过的模态</th><td>{(coverage.modalities_evaluated ?? []).join("、") || "无"}</td></tr>
          <tr><th>规则版本</th><td>{coverage.rules_version ?? "—"}</td></tr>
          <tr><th>适用控制点</th><td>{(coverage.control_points_applied ?? []).join("、") || "无"}</td></tr>
        </tbody>
      </table>

      <h2>命中的问题（只读）</h2>
      {ir.findings.length === 0 ? (
        <p>无</p>
      ) : (
        <table>
          <thead>
            <tr><th>finding</th><th>控制点</th><th>严重度</th><th>状态</th><th>原文</th><th>依据状态</th></tr>
          </thead>
          <tbody>
            {ir.findings.map((f) => (
              <tr key={f.finding_id}>
                <td>{f.finding_id}</td>
                <td>{f.control_code}</td>
                <td>{f.severity}</td>
                <td>{f.status}</td>
                <td>{f.quote ?? "—"}</td>
                <td>{f.authority_state ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>报告</h2>
      {reports.length === 0 ? (
        <p>暂无报告。</p>
      ) : (
        <ul>
          {reports.map((r) => (
            <li key={r.report_id}>
              <Link to={`/reports/${encodeURIComponent(r.report_id)}`}>{r.report_id}</Link>
              {r.published_at ? ` · ${r.published_at}` : ""}
            </li>
          ))}
        </ul>
      )}

      <p className="hint">
        IR：<code>{ir.ir_id}</code>（{ir.ir_version}） · receipt：<code>{ir.receipt_ref ?? "—"}</code>
      </p>
    </section>
  );
}
