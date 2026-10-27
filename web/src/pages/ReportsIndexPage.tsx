import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import LoadingRows from "../components/LoadingRows";
import { reviewApi, type ReportSummary } from "../api/client";
import Icon from "../ui/icon";

/**
 * 报告索引页（P-09 · Wave C）。
 *
 * 消费 `GET /api/v1/reports`，展示当前身份可读的全部不可变静态报告索引。
 */
export default function ReportsIndexPage() {
  const [rows, setRows] = useState<ReportSummary[] | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);

  useEffect(() => {
    let alive = true;
    reviewApi
      .listReports()
      .then((data) => {
        if (alive) setRows(data);
      })
      .catch((e: unknown) => {
        if (!alive) return;
        const err = e as { status?: number; message?: string };
        setError({ status: err.status ?? 0, message: err.message ?? String(e) });
      });
    return () => {
      alive = false;
    };
  }, []);

  if (error) {
    return (
      <section className="case">
        <h1>报告索引</h1>
        <div
          className={
            "state " +
            (error.status === 401 || error.status === 403
              ? "state--forbidden"
              : "state--error")
          }
          role="alert"
        >
          <h2>{error.status === 403 ? "无权读取报告列表" : "读取失败"}</h2>
          <p>{error.message}</p>
        </div>
      </section>
    );
  }

  return (
    <section className="cases-page" aria-labelledby="reports-index-title">
      <div className="cases-page__head">
        <div>
          <h1 id="reports-index-title">报告索引</h1>
          <p className="hint">
            归档已生成的合规审查报告。
          </p>
        </div>
        <span className="font-data hint">共 {(rows ?? []).length} 份报告</span>
      </div>

      {rows === null ? (
        <LoadingRows rows={3} label="正在加载报告列表" />
      ) : rows.length === 0 ? (
        <div className="state">
          <p className="hint">暂无可查阅的静态报告存档。</p>
        </div>
      ) : (
        <div className="cases-table-wrap">
          <table className="cases-table">
            <thead>
              <tr>
                <th scope="col">报告编号</th>
                <th scope="col">关联案件</th>
                <th scope="col">审查单号</th>
                <th scope="col">发布时刻</th>
                <th scope="col">存档文件</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.report_id}>
                  <td className="font-data">
                    <Link to={`/reports/${encodeURIComponent(r.report_id)}`}>
                      {r.report_id}
                    </Link>
                  </td>
                  <td className="font-data">
                    {r.case_id ? (
                      <Link to={`/cases/${encodeURIComponent(r.case_id)}`}>
                        {r.case_id}
                      </Link>
                    ) : (
                      "未登记"
                    )}
                  </td>
                  <td className="font-data">{r.ir_id ?? "未登记"}</td>
                  <td className="font-data">{r.published_at ?? "未发布"}</td>
                  <td className="font-data">
                    {r.url ? (
                      <a href={r.url} target="_blank" rel="noreferrer">
                        {r.url}
                      </a>
                    ) : (
                      "未生成"
                    )}
                  </td>
                  <td>
                    <Link
                      to={`/reports/${encodeURIComponent(r.report_id)}`}
                      className="btn"
                    >
                      查看报告 <Icon name="arrow-up-right" size={11} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
