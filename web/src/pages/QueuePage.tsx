import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useIdentity } from "../components/IdentitySwitcher";
import InlineMetricSummary from "../components/InlineMetricSummary";
import StatusBadge, { resolveDecisionBadge } from "../components/StatusBadge";
import Button from "../ui/Button";
import Icon from "../ui/icon";
import { QUEUE_LABELS, reviewApi, splitQueue, type CaseSummary } from "../api/client";
import { usePolling } from "../hooks/usePolling";
import { shouldSurfaceFailures } from "../hooks/polling.logic";
import CaseDetailPage from "./CaseDetailPage";

/**
 * 复核队列（P-05 · Wave B 同屏 Master-Detail 分诊 + 紧迫度排序 + J/K 键盘流）。
 *
 * 1. 口径：`GET /api/v1/queue` 只返回 REVIEW 与 待自决（A1）；
 * 2. 左栏展示高信息密度队列行（含内容首句摘要、高危计数、品线/渠道、认领状态），
 *    点击左栏 `<Link to="/cases/...">` 默认导航至独立详情页（保证 check_pages.mjs 契约全绿），
 *    同时每行提供「同屏分诊」按钮（或按 J/K 键）在右侧主栏直接内嵌渲染 CaseDetailPage！
 */

const FILTERS = [
  { key: "all", label: "全部待办" },
  { key: "REVIEW", label: "待人工复核" },
  { key: "待自决", label: "品牌自决" },
] as const;

const SORTS = [
  { key: "urgency", label: "按紧迫度" },
  { key: "newest", label: "按最新提交" },
] as const;

const SAMPLE_HIDDEN_KEY = "review-workbench.sample-hidden";

/** 五标签 → 徽标样式。语义色，**不使用品牌红**（DESIGN §7 / 断言 A6）。 */
export function stateBadge(state: string | null | undefined): {
  cls: string;
  text: string;
} {
  const b = resolveDecisionBadge(state);
  return { cls: b.cls, text: b.text };
}

function urgencyScore(c: CaseSummary): number {
  let score = (c.high_severity_count ?? 0) * 100;
  if (c.state === "REVIEW") score += 30;
  if (!c.assignee_id) score += 15;
  return score;
}

export default function QueuePage() {
  const { devEnabled, current, sessionEpoch } = useIdentity();
  const [rows, setRows] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("all");
  const [sortBy, setSortBy] = useState<(typeof SORTS)[number]["key"]>("urgency");
  const [sampleHidden, setSampleHidden] = useState<boolean>(() => {
    try {
      return window.localStorage.getItem(SAMPLE_HIDDEN_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [searchParams, setSearchParams] = useSearchParams();
  const previewCaseId = searchParams.get("caseId");

  // ★ ADR-0021 · W-3：队列页轮询。
  //
  //   改前是一次性 `useEffect` + `setRows(null)` 再取 —— 于是**永远不会自动刷新**，
  //   审核员必须手动 F5 才能看到新案件（多人协作时会漏案件 / 重复领取）。
  //
  //   三条口径都落在 `usePolling` 里：
  //   ① 标签页隐藏时停表（不是跳过）
  //   ② 回到可见时**立刻**拉一次（不等满 20 秒，否则旧数据看起来像新的）
  //   ③ 刷新**不清空**已有数据 —— 所以这里改成「只在首次把 rows 置 null」。
  //      改前每次取数都 `setRows(null)`，那是首屏写法；搬进轮询就会每 20 秒白一下。
  const poll = usePolling(
    useCallback(async () => {
      // ★ 开发身份未就绪时不请求（保持既有行为），但**不报错**：
      //   `current === null` 是「还没切好身份」，不是「取数失败」。
      if (devEnabled && current === null) return;
      try {
        const data = await reviewApi.getQueue();
        setRows(data);
        setError(null);
      } catch (e: unknown) {
        const err = e as { status?: number; message?: string };
        setError({ status: err.status ?? 0, message: err.message ?? String(e) });
        // ★ 要 rethrow：`usePolling` 靠它的 catch 统计 `failures`。
        //   不抛的话 `failures` 恒 0，「后台刷新失败」那条提示永远不出现 ——
        //   而轮询失败是**最不该静默**的一类失败（界面上还是旧数据，看起来正常）。
        throw e;
      }
    }, [current, devEnabled]),
    {
      // 开发身份未就绪时不启用轮询（与上面的 guard 同一个条件，两处都要）
      enabled: !(devEnabled && current === null),
    },
  );

  // ★ 首次加载才清空；后续刷新保留旧数据（轮询不清空是 W-3 的核心口径）。
  //
  // ★★ **不能**把 `poll.phase` 放进依赖：phase 每轮都会变
  //   （initial → idle → refreshing → idle…），于是「phase === initial 时清空」
  //   会在每轮首次那一帧成立 —— 列表照样闪。第一版就是这么写的。
  //   正确写法：清空只跟「身份/会话变了」走（那是真的换了数据源），
  //   轮询本身从不清空。
  useEffect(() => {
    if (devEnabled && current === null) {
      setRows(null);
      setError(null);
      return;
    }
    // 身份就绪（或切换）时先清空：旧身份的案件不该留在屏幕上。
    setRows(null);
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, devEnabled, sessionEpoch]);

  const { queued: rawQueued, offQueue } = useMemo(
    () => splitQueue(rows ?? []),
    [rows],
  );

  const sampleCount = useMemo(
    () => rawQueued.filter((c) => c.sample === true).length,
    [rawQueued],
  );

  const queued = useMemo(
    () => (sampleHidden ? rawQueued.filter((c) => c.sample !== true) : rawQueued),
    [rawQueued, sampleHidden],
  );

  const visible = useMemo(() => {
    const base =
      filter === "all" ? [...queued] : queued.filter((c) => c.state === filter);
    if (sortBy === "urgency") {
      base.sort((a, b) => urgencyScore(b) - urgencyScore(a));
    } else {
      base.sort((a, b) =>
        String(b.created_at ?? "").localeCompare(String(a.created_at ?? "")),
      );
    }
    return base;
  }, [queued, filter, sortBy]);

  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of queued)
      m.set(String(c.state), (m.get(String(c.state)) ?? 0) + 1);
    return m;
  }, [queued]);

  const activeCaseId = useMemo(() => {
    if (previewCaseId && visible.some((c) => c.case_id === previewCaseId)) {
      return previewCaseId;
    }
    return null;
  }, [previewCaseId, visible]);

  // J / K 纯键盘上下切案（AX-2）
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (visible.length === 0) return;
      if (e.key === "j" || e.key === "J") {
        e.preventDefault();
        const idx = visible.findIndex((c) => c.case_id === activeCaseId);
        const next = visible[Math.min(visible.length - 1, idx + 1)] ?? visible[0];
        if (next) setSearchParams({ caseId: next.case_id }, { replace: true });
      } else if (e.key === "k" || e.key === "K") {
        e.preventDefault();
        const idx = visible.findIndex((c) => c.case_id === activeCaseId);
        const prev =
          idx > 0 ? visible[idx - 1] : visible[visible.length - 1];
        if (prev) setSearchParams({ caseId: prev.case_id }, { replace: true });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeCaseId, setSearchParams, visible]);

  const toggleSampleHidden = (hide: boolean) => {
    setSampleHidden(hide);
    try {
      if (hide) window.localStorage.setItem(SAMPLE_HIDDEN_KEY, "1");
      else window.localStorage.removeItem(SAMPLE_HIDDEN_KEY);
    } catch {
      /* ignore storage errors */
    }
  };

  if (error) {
    if (error.status === 401) {
      return (
        <section className="case">
          <h1>复核队列</h1>
          <div className="state state--forbidden" role="alert">
            <h2>需要登录</h2>
            <p>
              请先登录后访问。本地调试可在左侧边栏启用开发身份；
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
            <h2>无权读取</h2>
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
        {/* ★ ADR-0021 · W-3：轮询状态条。
            只在两种情况出现，**不占位**（不推挤列表）：
            · `refreshing` —— 后台正在更新（列表内容**保持不动**）
            · `failures` 连续 ≥2 —— 后台刷新失败（界面上还是旧数据，看起来正常，
              所以这里必须说一句，否则用户会以为「没有新案件」） */}
        {(poll.phase === "refreshing" || shouldSurfaceFailures(poll.failures)) && (
          <div
            className="hint"
            data-poll-status=""
            role="status"
            aria-live="polite"
            style={{ padding: "0 0 var(--space-2)" }}
          >
            {poll.phase === "refreshing"
              ? "正在更新队列…"
              : `后台刷新失败（连续 ${poll.failures} 次），当前显示的可能不是最新数据`}
            {poll.lastLoadedAt && (
              <span className="font-data">
                {" "}· 上次成功 {new Date(poll.lastLoadedAt).toLocaleTimeString()}
              </span>
            )}
          </div>
        )}
        {sampleCount > 0 && (
          <div className="sample-banner" data-sample-banner="">
            <span>
              <StatusBadge axis="sample" value="样例数据" />{" "}
              {sampleHidden
                ? `已隐藏 ${sampleCount} 条演示数据`
                : `当前包含 ${sampleCount} 条演示数据`}
            </span>
            <Button
              variant="secondary"
              data-clear-sample=""
              onClick={() => toggleSampleHidden(!sampleHidden)}
            >
              {sampleHidden ? "恢复样例" : "清空样例"}
            </Button>
          </div>
        )}

        <div className="queue__filters" role="group" aria-label="队列筛选与排序">
          {FILTERS.map((f) => {
            const n =
              f.key === "all" ? queued.length : counts.get(f.key) ?? 0;
            // 空分组不渲染：一枚「待人工复核（0）」只会让用户停下来想为什么是 0
            if (n === 0 && f.key !== "all") return null;
            return (
              <button
                key={f.key}
                type="button"
                className="queue__filter"
                data-queue-filter={f.key}
                aria-pressed={filter === f.key}
                onClick={() => setFilter(f.key)}
              >
                {f.label}（{n}）
              </button>
            );
          })}
          <span className="queue__sorts">
            {SORTS.map((s) => (
              <button
                key={s.key}
                type="button"
                className="queue__filter queue__filter--sort"
                aria-pressed={sortBy === s.key}
                onClick={() => setSortBy(s.key)}
              >
                {s.label}
              </button>
            ))}
          </span>
        </div>

        {/* ★ 本页只有一个 h1，在右侧主栏。左栏列表不再放 h1 ——
            两个 h1 会触发 a11y 的 h1-unique 断言（计数 2）。 */}

        {rows === null && (
          <div className="queue__skeleton" aria-busy="true">
            <span className="queue__skeleton-row" />
            <span className="queue__skeleton-row" />
            <span className="queue__skeleton-row" />
          </div>
        )}

        {rows !== null && queued.length === 0 && (
          <p className="hint">
            这里现在是空的 —— 没有等待人工判定、也没有等待品牌自决的内容。
          </p>
        )}

        {visible.map((c) => {
          const isSelected = activeCaseId === c.case_id;
          return (
            <div
              key={c.case_id}
              className={
                "queue__item-wrap" +
                (isSelected ? " queue__item-wrap--selected" : "")
              }
            >
              <Link
                to={`/cases/${encodeURIComponent(c.case_id)}`}
                className="queue__row"
                data-sample={c.sample === true ? "true" : undefined}
                aria-current={isSelected ? "true" : undefined}
              >
                {/* 双行制：主行 = 标题 + 严重度（至多一枚）；
                    副行 = 案件号与元信息。layer / assignee 是研发概念，不出列表。 */}
                <span className="queue__row-top">
                  <span className="queue__row-excerpt">
                    {c.title_or_excerpt || c.case_id}
                  </span>
                  {(c.high_severity_count ?? 0) > 0 && (
                    <span
                      className="badge badge--severity-high"
                      data-status-badge=""
                    >
                      高危×{c.high_severity_count}
                    </span>
                  )}
                </span>
                <span className="queue__row-meta">
                  <span className="queue__row-id font-data">{c.case_id}</span>
                  {c.product_line && <span>{c.product_line}</span>}
                  {c.entry_channel && <span>{c.entry_channel}</span>}
                  <StatusBadge axis="decision" value={c.state} />
                  {c.sample === true && (
                    <span className="badge badge--sample" data-status-badge="">
                      样例
                    </span>
                  )}
                </span>
              </Link>
              <div className="queue__row-actions">
                <button
                  type="button"
                  className="queue__preview-btn"
                  aria-pressed={isSelected}
                  onClick={() =>
                    setSearchParams(
                      isSelected ? {} : { caseId: c.case_id },
                      { replace: true },
                    )
                  }
                >
                  {isSelected ? "收起" : "在这里查看"}
                </button>
              </div>
            </div>
          );
        })}

        {offQueue.length > 0 && (
          <div className="state state--warn" role="alert">
            <h2>
              <Icon name="alert-triangle" size={13} /> 队列口径异常
            </h2>
            <p>
              已过滤 {offQueue.length} 条非待办状态的案件（
              {[...new Set(offQueue.map((c) => String(c.state)))].join(" / ")}）。
              待办队列只应有 {QUEUE_LABELS.join(" 与 ")}。已从列表里排除，但这条不该出现。
            </p>
          </div>
        )}
      </div>

      <div className="queue__detail-pane">
        <div className="queue__detail-header">
          <h1>待人工复核案件</h1>
        </div>
        <InlineMetricSummary
          scope="queue"
          countsLabel={`待办 ${queued.length} 条（待人工判定 ${counts.get("REVIEW") ?? 0} / 待品牌自决 ${counts.get("待自决") ?? 0}）`}
          trendLabel={null}
          untestedLabel={queued.length > 0 ? "partial" : "未测"}
        />
        {activeCaseId ? (
          <CaseDetailPage embeddedCaseId={activeCaseId} />
        ) : (
          <div className="case queue__detail-empty">
            <p className="queue__detail-empty-title">从左侧选择一条案件</p>
            <p className="hint">
              选中后这里会展开原文、查出的问题和可做的处置。
            </p>
            <Link to="/submit" className="btn">
              <Icon name="sparkles" size={11} /> 打开审核工作台
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
