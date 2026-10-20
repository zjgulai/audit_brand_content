import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { reviewApi, type ReportSummary } from "../api/client";

/**
 * 报告查看（A7 阅读栏）。
 *
 * 报告是**不可变静态存档**：本页只展示后端返回的元信息，不编辑、不重算。
 * 「没有报告」是一个真实状态，不是错误 —— 案件可能尚未产出报告。
 */
export default function ReportPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const [report, setReport] = useState<ReportSummary | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);

  useEffect(() => {
    if (!reportId) return;
    let alive = true;
    reviewApi
      .getReport(reportId)
      .then((r) => {
        if (alive) setReport(r);
      })
      .catch((e: unknown) => {
        if (!alive) return;
        const err = e as { status?: number; message?: string };
        setError({ status: err.status ?? 0, message: err.message ?? String(e) });
      });
    return () => {
      alive = false;
    };
  }, [reportId]);

  if (error) {
    const forbidden = error.status === 403 || error.status === 404;
    return (
      <section className="case">
        <h1>报告查看</h1>
        <div
          className={"state " + (forbidden ? "state--forbidden" : "state--error")}
          role="alert"
        >
          <h2>
            {error.status === 404
              ? "404 · 报告不存在"
              : error.status === 403
                ? "403 · 无权读取该报告"
                : "读取失败"}
          </h2>
          <p>{error.status === 404 ? "该报告编号没有对应的存档。" : error.message}</p>
        </div>
        <p>
          <Link to="/queue">← 返回复核队列</Link>
        </p>
      </section>
    );
  }

  if (!report) {
    return (
      <section className="case">
        <h1>报告查看</h1>
        <p className="hint">加载中…</p>
      </section>
    );
  }

  return (
    <section className="case">
      <h1>报告查看</h1>
      <dl className="facts">
        <dt>report_id</dt>
        <dd className="font-data">{report.report_id}</dd>
        <dt>case_id</dt>
        <dd className="font-data">
          {report.case_id ? (
            <Link to={`/cases/${encodeURIComponent(report.case_id)}`}>
              {report.case_id}
            </Link>
          ) : (
            "未登记"
          )}
        </dd>
        <dt>ir_id</dt>
        <dd className="font-data">{report.ir_id ?? "未登记"}</dd>
        <dt>发布时刻</dt>
        <dd className="font-data">{report.published_at ?? "未发布"}</dd>
        <dt>静态报告</dt>
        <dd>
          {report.url ? (
            <a href={report.url} target="_blank" rel="noreferrer">
              {report.url}
            </a>
          ) : (
            "未生成"
          )}
        </dd>
      </dl>
      <p className="hint">
        报告是不可变静态存档；本页只展示后端返回的元信息，不编辑、不重算。
        IR 变更会产生新报告文件，旧文件不改不删。
      </p>
      <p>
        <Link to="/queue">← 返回复核队列</Link>
      </p>
    </section>
  );
}
