import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FIVE_LABELS, reviewApi, type CaseSummary } from "../api/client";
import { useIdentity } from "../components/IdentitySwitcher";
import StatusBadge from "../components/StatusBadge";
import Button from "../ui/Button";
import Icon from "../ui/icon";

/**
 * 案件总览列表（P-03 · Wave B）。
 *
 * 消费 `GET /api/v1/cases`，支持按五标签（BLOCK / REVIEW / 未审查 / 待自决 / PASS）、
 * 品线、负责人、覆盖状态与关键词检索全部当前身份可读的案件（区别于只展示待办的 /queue）。
 */

export default function CasesPage() {
  const { devEnabled, current, sessionEpoch } = useIdentity();
  const [rows, setRows] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [labelFilter, setLabelFilter] = useState<string>("all");
  const [lineFilter, setLineFilter] = useState<string>("all");
  const [query, setQuery] = useState<string>("");

  useEffect(() => {
    if (devEnabled && current === null) {
      setRows(null);
      setError(null);
      return;
    }
    let alive = true;
    setRows(null);
    setError(null);
    reviewApi
      .listCases()
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
  }, [current, devEnabled, sessionEpoch]);

  const productLines = useMemo(() => {
    const s = new Set<string>();
    for (const c of rows ?? []) {
      if (c.product_line) s.add(c.product_line);
    }
    return [...s].sort();
  }, [rows]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (rows ?? []).filter((c) => {
      if (labelFilter !== "all" && c.state !== labelFilter) return false;
      if (lineFilter !== "all" && c.product_line !== lineFilter) return false;
      if (q) {
        const hay = `${c.case_id} ${c.title_or_excerpt ?? ""} ${c.product_line ?? ""} ${c.assignee_id ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [rows, labelFilter, lineFilter, query]);

  if (error) {
    return (
      <section className="case">
        <h1>案件总览</h1>
        <div
          className={
            "state " +
            (error.status === 401 || error.status === 403
              ? "state--forbidden"
              : "state--error")
          }
          role="alert"
        >
          <h2>
            {error.status === 401
              ? "401 · 需要登录"
              : error.status === 403
                ? "403 · 无权读取案件列表"
                : "读取失败"}
          </h2>
          <p>{error.message}</p>
        </div>
      </section>
    );
  }

  return (
    <section className="cases-page" aria-labelledby="cases-page-title">
      <div className="cases-page__head">
        <div>
          <h1 id="cases-page-title">内容审核全景</h1>
          <p className="hint">
            支持检索已归档与处理中的全部送审内容（含违规拦截、审核通过与待检测等全部状态；如需处理待办，请前往「待人工复核」）。
          </p>
        </div>
        <span className="font-data hint">
          共 {filtered.length} / {(rows ?? []).length} 条案件
        </span>
      </div>

      <div className="cases-toolbar" role="search" aria-label="案件多维筛选">
        <div className="queue__filters" role="group" aria-label="五标签筛选">
          <button
            type="button"
            className="queue__filter"
            aria-pressed={labelFilter === "all"}
            onClick={() => setLabelFilter("all")}
          >
            全部标签（{(rows ?? []).length}）
          </button>
          {FIVE_LABELS.map((lbl) => {
            const cnt = (rows ?? []).filter((r) => r.state === lbl).length;
            const friendlyName: Record<string, string> = {
              BLOCK: "违规拦截",
              REVIEW: "待人工复核",
              PASS: "审核通过",
              待自决: "品牌自决",
              未审查: "待检测",
            };
            return (
              <button
                key={lbl}
                type="button"
                className="queue__filter"
                aria-pressed={labelFilter === lbl}
                onClick={() => setLabelFilter(lbl)}
              >
                {friendlyName[lbl] || lbl}（{cnt}）
              </button>
            );
          })}
        </div>

        <div className="cases-toolbar__controls">
          <label htmlFor="cases-line-filter" className="hint">
            品线：
          </label>
          <select
            id="cases-line-filter"
            value={lineFilter}
            onChange={(e) => setLineFilter(e.target.value)}
            aria-label="按产品线过滤"
          >
            <option value="all">全部品线</option>
            {productLines.map((pl) => (
              <option key={pl} value={pl}>
                {pl}
              </option>
            ))}
          </select>

          <label htmlFor="cases-search-input" className="hint">
            搜索：
          </label>
          <input
            id="cases-search-input"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="按案件号 / 摘要 / 负责人检索…"
          />
          {(labelFilter !== "all" || lineFilter !== "all" || query) && (
            <Button
              variant="secondary"
              onClick={() => {
                setLabelFilter("all");
                setLineFilter("all");
                setQuery("");
              }}
            >
              重置筛选
            </Button>
          )}
        </div>
      </div>

      {rows === null ? (
        <p className="hint">加载中…</p>
      ) : filtered.length === 0 ? (
        <div className="state">
          <p className="hint">当前筛选条件下没有匹配的案件。</p>
        </div>
      ) : (
        <div className="cases-table-wrap">
          <table className="cases-table">
            <thead>
              <tr>
                <th scope="col">案件编号</th>
                <th scope="col">对外标签</th>
                <th scope="col">处置层</th>
                <th scope="col">覆盖状态</th>
                <th scope="col">内容摘要</th>
                <th scope="col">品线 / 渠道</th>
                <th scope="col">负责人</th>
                <th scope="col">放行状态</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.case_id}>
                  <td className="font-data">
                    <Link to={`/cases/${encodeURIComponent(c.case_id)}`}>
                      {c.case_id}
                    </Link>
                  </td>
                  <td>
                    <StatusBadge axis="decision" value={c.state} />
                  </td>
                  <td className="font-data">{c.layer ?? "未测"}</td>
                  <td>
                    <StatusBadge axis="coverage" value={c.coverage_state} />
                  </td>
                  <td className="cases-table__excerpt">
                    {c.title_or_excerpt ?? "（无文本摘要）"}
                  </td>
                  <td>
                    <span>{c.product_line ?? "未测"}</span>
                    {c.entry_channel && (
                      <span className="hint"> · {c.entry_channel}</span>
                    )}
                  </td>
                  <td className="font-data">{c.assignee_id ?? "未指派"}</td>
                  <td>{c.release_status ?? "待放行"}</td>
                  <td>
                    <Link
                      to={`/cases/${encodeURIComponent(c.case_id)}`}
                      className="btn"
                    >
                      深审 <Icon name="arrow-up-right" size={11} />
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
