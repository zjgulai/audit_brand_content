import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { reviewApi, type ReportSummary } from "../api/client";

export default function ReportPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const [report, setReport] = useState<ReportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!reportId) return;
    let alive = true;
    reviewApi
      .getReport(reportId)
      .then((r) => {
        if (alive) setReport(r);
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
  }, [reportId]);

  if (error) return <p className="error">读取失败：{error}</p>;
  if (!report) return <p>加载中…</p>;

  return (
    <section>
      <h1>报告查看</h1>
      <table>
        <tbody>
          <tr><th>report_id</th><td>{report.report_id}</td></tr>
          <tr><th>case_id</th><td>{report.case_id ?? "—"}</td></tr>
          <tr><th>ir_id</th><td>{report.ir_id ?? "—"}</td></tr>
          <tr><th>发布时刻</th><td>{report.published_at ?? "—"}</td></tr>
          <tr>
            <th>静态报告</th>
            <td>
              {report.url ? (
                <a href={report.url} target="_blank" rel="noreferrer">
                  {report.url}
                </a>
              ) : (
                "—"
              )}
            </td>
          </tr>
        </tbody>
      </table>
      <p className="hint">
        报告是不可变静态存档；本页只展示后端返回的元信息，不编辑、不重算。
      </p>
    </section>
  );
}
