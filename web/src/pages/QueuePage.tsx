import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { QUEUE_LABELS, reviewApi, splitQueue, type CaseSummary } from "../api/client";

/**
 * 复核队列（A1 Triage queue）。
 *
 * 口径：`GET /api/v1/queue` 只返回 REVIEW 与 待自决。
 * 若后端仍返回别的标签（例如代理没关 /queue 那个联调别名），
 * `splitQueue` 会把它们挑出来，页面上**明说「口径异常」**——
 * 静默 filter 掉会让这个 bug 永远看不见（断言 A1 的反向对照要的就是「它不出现」）。
 */

const FILTERS = [
  { key: "all", label: "全部待办" },
  { key: "REVIEW", label: "REVIEW" },
  { key: "待自决", label: "待自决" },
] as const;

/** 五标签 → 徽标样式。语义色，**不使用品牌红**（DESIGN §7 / 断言 A6）。 */
export function stateBadge(state: string | null | undefined): {
  cls: string;
  text: string;
} {
  switch (state) {
    case "BLOCK":
      return { cls: "badge badge--block", text: "BLOCK" };
    case "REVIEW":
      return { cls: "badge badge--review", text: "REVIEW" };
    case "PASS":
      return { cls: "badge badge--pass", text: "PASS" };
    case "待自决":
      return { cls: "badge badge--pending", text: "待自决" };
    case "未审查":
      return { cls: "badge badge--untested", text: "未审查" };
    default:
      // ★ 不许折叠成「—」或空：未测是独立状态，不是缺值（断言 A2）
      return { cls: "badge badge--untested", text: "未测" };
  }
}

export default function QueuePage() {
  const [rows, setRows] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("all");
  const { pathname } = useLocation();

  useEffect(() => {
    let alive = true;
    reviewApi
      .getQueue()
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

  const { queued, offQueue } = useMemo(
    () => splitQueue(rows ?? []),
    [rows],
  );

  const visible = useMemo(() => {
    if (filter === "all") return queued;
    return queued.filter((c) => c.state === filter);
  }, [queued, filter]);

  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of queued) m.set(String(c.state), (m.get(String(c.state)) ?? 0) + 1);
    return m;
  }, [queued]);

  if (error) {
    if (error.status === 401) {
      return (
        <section className="case">
          <h1>复核队列</h1>
          <div className="state state--forbidden" role="alert">
            <h2>401 · 需要登录</h2>
            <p>
              后端要求有效 session。本机联调时，请在上方「身份」下拉里选一个身份；
              生产环境走飞书 OAuth / SSO。
            </p>
          </div>
        </section>
      );
    }
    if (error.status === 403) {
      return (
        <section className="case">
          <h1>复核队列</h1>
          <div className="state state--forbidden" role="alert">
            <h2>403 · 无权读取</h2>
            <p>
              当前身份没有可读的案件（受 tenant + product_line + assigned/actionable 约束）。
              换一个身份，或申请相应权限。
            </p>
          </div>
        </section>
      );
    }
    return (
      <section className="case">
        <h1>复核队列</h1>
        <div className="state state--error" role="alert">
          读取失败：{error.message}
        </div>
      </section>
    );
  }

  return (
    <div className="queue">
      <div className="queue__list">
        <div className="queue__filters" role="group" aria-label="队列筛选">
          {FILTERS.map((f) => {
            const n = f.key === "all" ? queued.length : counts.get(f.key) ?? 0;
            return (
              <button
                key={f.key}
                type="button"
                className="queue__filter"
                aria-pressed={filter === f.key}
                onClick={() => setFilter(f.key)}
              >
                {f.label}（{n}）
              </button>
            );
          })}
        </div>

        {/* ★ 本页只有一个 h1，在右侧主栏。左栏列表不再放 h1 ——
            两个 h1 会触发 a11y 的 h1-unique 断言（计数 2）。 */}

        {rows === null && <p className="hint" style={{ padding: "0.7rem" }}>加载中…</p>}

        {rows !== null && queued.length === 0 && (
          <p className="hint" style={{ padding: "0.7rem" }}>
            队列为空 —— 没有处于 REVIEW 或 待自决 的案件。
          </p>
        )}

        {visible.map((c) => {
          const b = stateBadge(c.state);
          return (
            <Link
              key={c.case_id}
              to={`/cases/${encodeURIComponent(c.case_id)}`}
              className="queue__row"
              aria-current={pathname === `/cases/${c.case_id}` ? "true" : undefined}
            >
              <span className="queue__row-top">
                <span className="queue__row-id font-data">{c.case_id}</span>
                <span className={b.cls}>{b.text}</span>
              </span>
              <span className="queue__row-meta">
                <span className="font-data">{c.layer ?? "未测"}</span>
                <span>{c.product_line ?? "未测"}</span>
                <span className="font-data">{c.assignee_id ?? "未指派"}</span>
              </span>
            </Link>
          );
        })}

        {offQueue.length > 0 && (
          <div className="state state--warn" role="alert" style={{ margin: "0.7rem" }}>
            <h2>⚠ 队列口径异常</h2>
            <p>
              后端返回了 {offQueue.length} 条不属于待办队列的案件（
              {[...new Set(offQueue.map((c) => String(c.state)))].join(" / ")}）。
              待办队列只应有 {QUEUE_LABELS.join(" 与 ")}。已从列表里排除，但这条不该出现。
            </p>
          </div>
        )}
      </div>

      <div className="case">
        <h1>复核队列</h1>
        <p className="hint">
          选择左侧一条案件查看判定与证据链。队列只读；复核动作在案件详情页进行。
        </p>
      </div>
    </div>
  );
}
