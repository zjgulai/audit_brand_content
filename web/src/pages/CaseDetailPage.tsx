import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  reviewApi,
  type CaseDetail,
  type Finding,
  type NotEvaluated,
  type ReportSummary,
} from "../api/client";
import { stateBadge } from "./QueuePage";
import { useIdentity } from "../components/IdentitySwitcher";
import taxonomy from "../data/taxonomy.json";

/**
 * 案件详情（A7 Research brief）。
 *
 * 这一屏的智能体时刻是「解释判定」——**纯本地渲染，不接模型**
 * （api/ 与 base/ 零 LLM 依赖，这是要保住的性质）。
 *
 * 它做三件事，全部可由字段核对，不编造：
 *   1. 把每条 finding 还原成「命中哪条规则 · 原文在哪 · 依据能不能核」
 *   2. 说清覆盖是 partial 还是 full，以及哪几族**根本没跑**（不是 0）
 *   3. 显示复核台账摘要；开发验收可动态加载人工写动作，生产构建保持只读
 */

const WHY_TEXT: Record<string, string> = {
  not_wired: "未接线（根本没跑，不是跑了没问题）",
  no_rule: "无适用规则",
  no_capability: "无该能力",
};

const AUTHORITY_TEXT: Record<string, string> = {
  ok: "可核",
  expired: "依据已过期",
  missing: "依据缺失",
};

interface SpecMeta {
  spec_version?: string;
  spec_fingerprint?: string;
  boundary_disputes?: Array<{
    rule_id?: string;
    section?: string;
    axis_code?: string | null;
    dispute?: string;
    status?: string;
    resolved_in?: string | null;
  }>;
}

const meta = (taxonomy as { meta?: SpecMeta }).meta ?? {};
const DevReviewActions = __REVIEW_WRITE_ENABLED__
  ? lazy(() => import("../components/DevReviewActions"))
  : null;

/**
 * ★ 2026-10-20 删掉了一段死代码，记在这里因为它长得太像在工作：
 *
 * 原先有 `disputeOf(ruleId)`，按 `rule_id` 精确匹配 `meta.boundary_disputes`，
 * 但调用处写的是 `disputeOf(f.control_code)` —— 实参形如 `H02`，
 * 而 disputes 的键形如 `r-724b26ecb1dee9c4`。**永远不相等**，
 * 欠定徽标一次都没渲染过，而类型检查、构建、A8 全绿。
 *
 * 更根本的是：**`Finding` 契约里没有 `rule_id`**
 * （`api/review_api.py` 的 `class Finding` 只有 finding_id / control_code /
 * status / severity / ... 见断言 A10）。所以「按 rule_id 关联 finding 与欠定条目」
 * 这件事**在当前契约下无法成立**，不是查法写错。
 *
 * 现在改成：不假装能逐条关联，在证据链旁边如实说明这条断层。
 */

/**
 * 本页能诚实说的：规范登记了若干欠定条目，但 finding 侧没有能与之对上的键。
 *
 * ★ 措辞经过一次更正（4b，2026-10-20）。原先写「这不等于『没有落上』—— 是查不了」，
 *   但「查不了」和「没有落上」在界面上长得一样，都会被复核员读成「这里没问题」。
 *   最后一句必须是**否定式的那半句**：只说明关联做不到，不说明本案件不落在其中。
 */
function SpecSeamNote({ disputeCount }: { disputeCount: number }) {
  if (disputeCount === 0) return null;
  return (
    <div className="state state--warn" role="note" style={{ margin: "0 0 0.6rem" }}>
      <strong>规范有 {disputeCount} 条已登记欠定边界，本页无法逐条关联</strong>
      <p style={{ margin: "0.3rem 0 0" }}>
        <code>Finding.control_code</code>（形如 H02）与{" "}
        <code>boundary_disputes[].rule_id</code>（形如 r-724b26ec…）不是同一个键，
        而欠定条目描述里的条款号（DSC12 / FCT5 / FCT2）同样对不上，
        所以无法判断某条 finding 是否落在其中。
      </p>
      <p style={{ margin: "0.3rem 0 0" }}>
        <b>这只说明关联做不到，不说明本案件不落在其中任何一条。</b>
        欠定条目本身见「分类规范」页。
      </p>
    </div>
  );
}

function EvidenceItem({ f, index }: { f: Finding; index: number }) {
  const quote = f.quote;
  const isLong = typeof quote === "string" && quote.length > 180;
  const authority = String(f.authority_state ?? "ok");
  const authText = AUTHORITY_TEXT[authority] ?? authority;

  return (
    <li className="evidence__item">
      <div className="evidence__head">
        <span className="font-data" style={{ fontWeight: 600 }}>
          {index + 1}. {f.control_code}
        </span>
        <span className="font-data" style={{ color: "hsl(var(--muted-foreground))" }}>
          {f.finding_id}
        </span>
        <span className="badge badge--partial">{f.severity}</span>
        <span className="hint">{f.status === "candidate" ? "候选（待裁）" : f.status}</span>
      </div>

      {quote === null || quote === undefined ? (
        // ★ 空原文是「没有」，不是「空字符串」——必须明说（断言 A2 的近亲）
        <div className="evidence__quote evidence__quote--empty">无原文引用</div>
      ) : (
        <div
          className={
            "evidence__quote" + (isLong ? " evidence__quote--long" : "")
          }
        >
          {quote}
        </div>
      )}

      <div className="evidence__why">
        {f.location && f.location.start !== undefined ? (
          <span className="evidence__loc font-data">
            位置 {f.location.type ?? "text"} · {f.location.start}–{f.location.end}
            {"　"}
          </span>
        ) : null}
        <span>
          依据：{(f.authority_ref ?? []).map((r) => r.ref_id).join("、") || "未登记"}
          {" · "}
          <span
            style={{
              color:
                authority === "ok"
                  ? "hsl(var(--ok))"
                  : "hsl(var(--bad))",
              fontWeight: 600,
            }}
          >
            {authText}
          </span>
        </span>
        {f.derived_from && (
          <>
            {"　"}由 <span className="font-data">{f.derived_from}</span> 派生
          </>
        )}
      </div>

      {f.rule_conflict && (
        <div className="state state--warn" style={{ margin: "0.35rem 0 0" }}>
          <strong>规则冲突</strong>
          ：这条 finding 涉及两条互相矛盾的依据，<strong>须人工裁定</strong>，不静默取一。
          {f.resolution_detail?.reason ? `（${f.resolution_detail.reason}）` : ""}
        </div>
      )}
    </li>
  );
}

function NotEvaluatedList({ items }: { items: NotEvaluated[] }) {
  if (items.length === 0) {
    // 没跑 vs 跑了没问题：这里「没有未评估项」才是真的全覆盖
    return <p className="hint">无未评估项（所有适用控制点都已跑过）。</p>;
  }
  return (
    <ul className="notrun">
      {items.map((it, i) => (
        <li key={i}>
          <span>{it.what ?? "未命名控制点"}</span>
          <span className="notrun__why">
            {WHY_TEXT[String(it.why)] ?? String(it.why ?? "未说明")}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { devEnabled, current, sessionEpoch } = useIdentity();
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const requestGeneration = useRef(0);

  const readCase = useCallback(async () => {
    if (!caseId) throw new Error("缺少案件编号");
    const [caseDetail, reportRows] = await Promise.all([
      reviewApi.getCase(caseId),
      reviewApi.listReports(),
    ]);
    return {
      caseDetail,
      reports: reportRows.filter((report) => report.case_id === caseId),
    };
  }, [caseId]);

  const applyReadback = useCallback(
    (result: { caseDetail: CaseDetail; reports: ReportSummary[] }) => {
      setDetail(result.caseDetail);
      setReports(result.reports);
      setError(null);
      return result.caseDetail;
    },
    [],
  );

  const refreshAfterWrite = useCallback(async () => {
    const generation = requestGeneration.current;
    try {
      const result = await readCase();
      if (generation !== requestGeneration.current) return null;
      return applyReadback(result);
    } catch {
      return null;
    }
  }, [applyReadback, readCase]);

  const load = useCallback(async () => {
    if (!caseId) return null;
    const generation = ++requestGeneration.current;
    try {
      const result = await readCase();
      if (generation !== requestGeneration.current) return null;
      return applyReadback(result);
    } catch (cause: unknown) {
      if (generation !== requestGeneration.current) return null;
      const err = cause as { status?: number; message?: string };
      setError({ status: err.status ?? 0, message: err.message ?? String(cause) });
      return null;
    }
  }, [applyReadback, caseId, readCase]);

  useEffect(() => {
    requestGeneration.current += 1;
    setDetail(null);
    setReports([]);
    setError(null);
    if (!devEnabled || current !== null) void load();
  }, [caseId, current, devEnabled, load, sessionEpoch]);

  if (error) {
    const head = error.status === 403 ? "403 · 无权读取该案件" : error.status === 404 ? "404 · 案件不存在" : "读取失败";
    return (
      <section className="case">
        <h1>案件详情</h1>
        <div
          className={"state " + (error.status === 403 || error.status === 404 ? "state--forbidden" : "state--error")}
          role="alert"
        >
          <h2>{head}</h2>
          <p>{error.status === 403 ? "当前身份不在该案件的可见范围内（tenant + product_line + assigned/actionable）。" : error.message}</p>
        </div>
        <p>
          <Link to="/queue">← 返回复核队列</Link>
        </p>
      </section>
    );
  }

  if (!detail) {
    return (
      <section className="case">
        <h1>案件详情</h1>
        <p className="hint">加载中…</p>
      </section>
    );
  }

  const ir = detail.ir;
  const dec = ir.decision;
  const cov = ir.coverage;
  const badge = stateBadge(dec.state);
  const partial = cov.coverage_state === "partial";
  const notEvaluated = cov.not_evaluated_reason ?? [];
  const isCandidate = (ir.findings ?? []).some((f) => f.status === "candidate");
  const review = detail.review;
  const leaseActive =
    typeof review?.lease_expires === "number" && review.lease_expires > Date.now() / 1000;

  return (
    <section className="case">
      <div className="case__head">
        <h1>案件详情</h1>
        <span className={badge.cls}>{badge.text}</span>
        <span className="font-data" style={{ fontSize: 12 }}>
          {detail.case_id}
        </span>
      </div>
      <p className="case__sub">
        <span className="font-data">{ir.ir_id}</span>（{ir.ir_version}） · 回执{" "}
        <span className="font-data">{ir.receipt_ref ?? "未测"}</span>
        {ir.created_at && <> · {ir.created_at}</>}
      </p>

      <h2>判定</h2>
      <dl className="facts">
        <dt>对外标签</dt>
        <dd>
          {badge.text} <span className="hint">（{dec.layer} · 唯一判定由后端产出）</span>
        </dd>
        <dt>放行状态</dt>
        <dd>
          {dec.release_status}
          <span className="hint"> —— 机器与前端都不得改；只由人经 release-decision 变更</span>
        </dd>
        <dt>并行义务</dt>
        <dd>{(dec.obligations ?? []).join("、") || "无"}</dd>
      </dl>

      <h2>覆盖证明</h2>
      <dl className="facts">
        <dt>覆盖状态</dt>
        <dd>
          <span className={`badge ${partial ? "badge--partial" : "badge--pass"}`}>
            {partial ? "partial" : cov.coverage_state}
          </span>
          {partial && (
            <span style={{ marginLeft: "0.5rem", fontWeight: 600 }}>
              仅已覆盖部分可判
            </span>
          )}
        </dd>
        <dt>评过的模态</dt>
        <dd>{(cov.modalities_evaluated ?? []).join("、") || "未测"}</dd>
        <dt>适用控制点</dt>
        <dd className="font-data">
          {(cov.control_points_applied ?? []).join("、") || "无"}
        </dd>
        <dt>规则版本</dt>
        <dd className="font-data" style={{ fontSize: 11 }}>
          {cov.rules_version ?? "未测"}
        </dd>
        <dt>分类规范</dt>
        <dd className="spec-version">
          {/* ★ 断言 A9：spec_version 与 spec_fingerprint 必须同时出现 */}
          <span>按 spec {meta.spec_version ?? "未测"}</span>
          <span className="font-data">{meta.spec_fingerprint ?? "未测"}</span>
        </dd>
      </dl>

      <h2>未评估（不是 0，是没跑）</h2>
      <NotEvaluatedList items={notEvaluated} />

      <h2>证据链（智能体时刻 · 本地渲染，不接模型）</h2>
      <SpecSeamNote disputeCount={(meta.boundary_disputes ?? []).length} />
      {(ir.findings ?? []).length === 0 ? (
        <p className="hint">无 finding。</p>
      ) : (
        <ol className="evidence" style={{ paddingLeft: 0 }}>
          {(ir.findings ?? []).map((f, i) => (
            <EvidenceItem key={f.finding_id} f={f} index={i} />
          ))}
        </ol>
      )}

      <h2>报告</h2>
      {reports.length === 0 ? (
        <p className="hint">暂无报告。</p>
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

      <div className="actions">
        <h2 style={{ marginTop: 0, border: "none", paddingBottom: 0 }}>复核动作</h2>
        <dl className="facts">
          <dt>台账状态</dt>
          <dd>{review?.status ?? "未读取"}</dd>
          <dt>负责人</dt>
          <dd>{review?.assignee ?? "未认领"}</dd>
          <dt>台账版本</dt>
          <dd className="font-data">{review?.version ?? "未读取"}</dd>
          <dt>租约</dt>
          <dd>
            {review?.lease_expires
              ? `${leaseActive ? "有效至" : "已过期于"} ${new Date(review.lease_expires * 1000).toLocaleString()}`
              : "无"}
          </dd>
          <dt>主草稿</dt>
          <dd className="font-data">{review?.primary_draft_id ?? "无"}</dd>
          <dt>正式记录</dt>
          <dd>当前 GET 不返回 formal 摘要</dd>
        </dl>
        {__REVIEW_WRITE_ENABLED__ && DevReviewActions ? (
          current ? (
            <Suspense fallback={<p className="hint">加载开发写动作…</p>}>
              <DevReviewActions
                key={`${detail.case_id}:${current.id}`}
                detail={detail}
                refresh={refreshAfterWrite}
              />
            </Suspense>
          ) : (
            <div className="state state--warn" role="note">
              只读：先显式启用本地开发身份。身份未建立前不会加载写动作。
            </div>
          )
        ) : (
          <div className="state state--warn" role="note">
            只读：生产认证写入口尚未接入，生产构建不包含人工写动作模块。
          </div>
        )}
        <div className="actions__row" style={{ marginTop: "0.6rem" }}>
          {isCandidate && (
            <>
              {/*
                ★ 2026-10-20：这两个按钮**刻意禁用**，不是没做完。
                实测证据（两条，缺一条都不成立）：
                  1. api/review_api.py:377 是 `FindingStore()` —— 空仓库，
                     从没从投影载入任何 finding。对真实案件调 confirm 返回
                     404「finding 不存在」。
                  2. 即使载入了，读侧也看不见：GET /cases/{id} 的 ir 直接取
                     投影文件（`case["ir"]`），而 finding_store 在 review_api.py
                     里一次都没被读过（grep `.active()` → 0 命中）。
                 于是 write_api 写 finding_store、read_api 读投影文件，
                 两条路不通。修它要决定「ir.findings 的真相源是谁」，
                 属 ADR 级变更，不在 Web 范围内。
                 见 web/docs/handoff-4b.md §五。
              */}
              <button
                type="button"
                className="btn"
                disabled
                title="后端 finding_store 未接线，确认后不会反映到 ir.findings"
              >
                确认 finding
              </button>
              <button
                type="button"
                className="btn"
                disabled
                title="后端 finding_store 未接线，驳回后不会反映到 ir.findings"
              >
                驳回 finding
              </button>
            </>
          )}
        </div>
        {isCandidate && (
          <div className="state state--warn" role="note" style={{ marginTop: "0.5rem" }}>
            <strong>逐条确认 / 驳回暂不可用（不是没做完，是后端未接线）</strong>
            <p style={{ margin: "0.3rem 0 0" }}>
              写端点 <code>POST /cases/{"{id}"}/actions</code> 的 confirm / reject
              会写进 <code>finding_store</code>，但该仓库是空的
              （<code>api/review_api.py:377</code> 未从投影载入），
              且读侧 <code>GET /cases/{"{id}"}</code> 的 findings 直接取自投影文件、
              从不读 <code>finding_store</code>。两条路不通 ——
              点了也看不到变化，所以这里禁用，而不是假装能点。
            </p>
          </div>
        )}
        <p className="actions__note">
          {__REVIEW_WRITE_ENABLED__ && DevReviewActions
            ? current
              ? `当前开发身份：${current.label}（${current.id}）。人工意见不改变机器标签或放行状态。`
              : "当前没有开发 session；页面保持只读。"
            : "生产构建保持只读；真实认证与持久写链另行验收。"}
        </p>
      </div>

      <p style={{ marginTop: "1.5rem" }}>
        <Link to="/queue">← 返回复核队列</Link>
      </p>
    </section>
  );
}
