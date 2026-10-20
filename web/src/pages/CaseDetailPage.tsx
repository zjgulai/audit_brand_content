import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ApiError,
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
 *   3. 让人动手：认领 / 存草稿 / 提交结论 —— 且都必须经写 API
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

/** 规则号 → 争议登记（按 rule_id 精确匹配，不做模糊）。 */
function disputeOf(ruleId: string | null | undefined) {
  if (!ruleId) return null;
  return (
    (meta.boundary_disputes ?? []).find((d) => d.rule_id === ruleId) ?? null
  );
}

function EvidenceItem({ f, index }: { f: Finding; index: number }) {
  const quote = f.quote;
  const isLong = typeof quote === "string" && quote.length > 180;
  const authority = String(f.authority_state ?? "ok");
  const authText = AUTHORITY_TEXT[authority] ?? authority;
  const dispute = disputeOf(f.control_code);

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

      {dispute && (
        <div className="state state--warn" style={{ margin: "0.35rem 0 0" }}>
          <strong>规范欠定（{dispute.section}）</strong>
          ：{dispute.dispute}
          {dispute.axis_code === null && " —— 多轴争议，规范没有给出单一轴"}
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
  const { current } = useIdentity();
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [flash, setFlash] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const load = useCallback(() => {
    if (!caseId) return;
    let alive = true;
    Promise.all([reviewApi.getCase(caseId), reviewApi.listReports()])
      .then(([caseDetail, reportRows]) => {
        if (!alive) return;
        setDetail(caseDetail);
        setReports(reportRows.filter((r) => r.case_id === caseId));
        setError(null);
      })
      .catch((e: unknown) => {
        if (!alive) return;
        const err = e as { status?: number; message?: string };
        setError({ status: err.status ?? 0, message: err.message ?? String(e) });
      });
    return () => {
      alive = false;
    };
  }, [caseId]);

  useEffect(() => load(), [load]);

  const act = async (name: string, fn: () => Promise<unknown>) => {
    setBusy(name);
    setFlash(null);
    try {
      await fn();
      setFlash({ kind: "ok", text: `${name} 已提交` });
      load();
    } catch (e: unknown) {
      if (e instanceof ApiError) {
        const why =
          e.status === 409
            ? "版本冲突：案件已被他人改动，请刷新后重试"
            : e.status === 403
              ? "无权执行该动作"
              : e.message;
        setFlash({ kind: "error", text: `${name} 失败（${e.status}）：${why}` });
      } else {
        setFlash({ kind: "error", text: `${name} 失败：${String(e)}` });
      }
    } finally {
      setBusy(null);
    }
  };

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
        {flash && (
          <div
            className={"state " + (flash.kind === "error" ? "state--error" : "state--warn")}
            role="status"
            style={{ marginTop: 0 }}
          >
            {flash.text}
          </div>
        )}
        <label htmlFor="review-note">理由 / 备注（存草稿或提交时一并记录）</label>
        <textarea
          id="review-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="写清依据与判断；空理由的提交不构成复核结论。"
        />
        <div className="actions__row" style={{ marginTop: "0.6rem" }}>
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy !== null}
            onClick={() => act("认领", () => reviewApi.claim(detail.case_id))}
          >
            认领
          </button>
          <button
            type="button"
            className="btn"
            disabled={busy !== null || note.trim() === ""}
            onClick={() =>
              act("存草稿", () =>
                reviewApi.saveDraft(detail.case_id, 0, { notes: note }),
              )
            }
            title={note.trim() === "" ? "先写理由" : undefined}
          >
            存草稿
          </button>
          <button
            type="button"
            className="btn"
            disabled={busy !== null || note.trim() === ""}
            onClick={() =>
              act("提交结论", () =>
                reviewApi.submitConclusion(detail.case_id, 0, {
                  notes: note,
                  state: dec.state,
                }),
              )
            }
            title={note.trim() === "" ? "先写理由" : undefined}
          >
            提交结论
          </button>
          {isCandidate && (
            <span className="hint">
              有候选 finding：可回到证据链逐条确认 / 驳回（待接）。
            </span>
          )}
        </div>
        <p className="actions__note">
          当前身份：{current?.label ?? "未选择"}（{current?.id ?? "未选择"}）。
          所有动作经写 API，前端不构造状态变更；版本冲突会返回 409。
        </p>
      </div>

      <p style={{ marginTop: "1.5rem" }}>
        <Link to="/queue">← 返回复核队列</Link>
      </p>
    </section>
  );
}
