import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { reviewApi, type CaseSummary } from "../api/client";

export default function QueuePage() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    reviewApi
      .getQueue()
      .then((rows) => {
        if (alive) setCases(rows);
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section>
      <h1>复核队列</h1>
      {error && <p className="error">读取失败：{error}</p>}
      {!error && cases === null && <p>加载中…</p>}
      {!error && cases !== null && cases.length === 0 && <p>队列为空。</p>}
      {!error && cases !== null && cases.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>案件</th>
              <th>状态</th>
              <th>层</th>
              <th>放行状态</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.case_id}>
                <td>
                  <Link to={`/cases/${encodeURIComponent(c.case_id)}`}>
                    {c.case_id}
                  </Link>
                </td>
                <td>{c.state ?? "—"}</td>
                <td>{c.layer ?? "—"}</td>
                <td>{c.release_status ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="hint">
        队列只读；分派、claim、复核动作与签发入口均不在阶段一 Web 提供。
      </p>
    </section>
  );
}
