import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ApiError,
  reviewApi,
  type CaseDetail,
  type Finding,
  type NotEvaluated,
  type ReportSummary,
} from "../api/client";
import ContentUnitViewer from "../components/ContentUnitViewer";
import { useIdentity } from "../components/IdentitySwitcher";
import InlineMetricSummary from "../components/InlineMetricSummary";
import ReviewActions from "../components/ReviewActions";
import StatusBadge, {
  resolveAuthorityState,
  resolveCoverageBadge,
} from "../components/StatusBadge";
import Button from "../ui/Button";
import Icon from "../ui/icon";
import taxonomy from "../data/taxonomy.json";

/**
 * 案件深度审查页（P-04 · Wave B 双栏高亮联动 + 证据链就地裁决）。
 *
 * 1. 左栏展示 ContentUnit 原件（归一化正文、结构化字段、覆盖边界与双指纹），
 *    与右栏证据链双向点击定位高亮（修复 D-04「盲审」缺陷）；
 * 2. 右栏证据链内每条 candidate finding 支持直接点击「确认 / 驳回」就地裁决（修复 D-08 空间割裂）；
 * 3. 规则冲突（rule_conflict=true）并排展示冲突依据卡片（修复 D-09）；
 * 4. 既可作为独立双栏页面 `/cases/:caseId` 打开，也可由 `QueuePage` 右侧内嵌调用（`embeddedCaseId`）。
 */

const WHY_TEXT: Record<string, string> = {
  not_wired: "未接线（根本没跑，不是跑了没问题）",
  no_rule: "无适用规则",
  no_capability: "无该能力",
  no_control_points: "未做，这一族还没有定控制点",
};

interface SpecMeta {
  spec_version?: string;
  spec_fingerprint?: string;
}

const meta = (taxonomy as { meta?: SpecMeta }).meta ?? {};
const DevReviewActions = __REVIEW_WRITE_ENABLED__
  ? lazy(() => import("../components/DevReviewActions"))
  : null;

function SpecSeamNote({ disputeCount }: { disputeCount: number }) {
  if (disputeCount === 0) return null;
  return (
    <div className="state state--warn" role="note">
      有 {disputeCount} 条规则条目尚在修订中，暂时无法与本案的发现逐条对应；
      条目详情见「分类规范」。这不影响本页已给出的判定。
    </div>
  );
}

interface EvidenceItemProps {
  f: Finding;
  index: number;
  isActive: boolean;
  canAdjudicate: boolean;
  caseId: string;
  version: number | null;
  adjudicatedStatus?: "confirmed" | "rejected";
  onLocate: (findingId: string) => void;
  onAdjudicated: (
    findingId: string,
    newStatus: "confirmed" | "rejected",
  ) => Promise<CaseDetail | null>;
}

function EvidenceItem({
  f,
  index,
  isActive,
  canAdjudicate,
  caseId,
  version,
  adjudicatedStatus,
  onLocate,
  onAdjudicated,
}: EvidenceItemProps) {
  const quote = f.quote;
  const isLong = typeof quote === "string" && quote.length > 180;
  // ★ 修 D-01 / 断言 A2d：authority_state 缺失绝不默认 "ok"（可核），必须落「未测」
  const authInfo = resolveAuthorityState(f.authority_state);
  const conflictRefs = f.resolution_detail?.refs ?? [];
  const effectiveStatus = adjudicatedStatus ?? f.status;
  const [reason, setReason] = useState("");
  const [showReason, setShowReason] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [itemMsg, setItemMsg] = useState<{ ok: boolean; text: string } | null>(
    null,
  );

  const handleAdjudicate = async (decision: "confirm" | "reject") => {
    if (version === null || busy !== null) return;
    setBusy(decision);
    setItemMsg(null);
    try {
      const { reviewWriteApi } = await import("../api/write-client");
      const key = crypto.randomUUID();
      if (decision === "confirm") {
        await reviewWriteApi.confirmFinding(
          caseId,
          version,
          f.finding_id,
          reason,
          key,
        );
      } else {
        await reviewWriteApi.rejectFinding(
          caseId,
          version,
          f.finding_id,
          reason,
          key,
        );
      }
      const nextStatus = decision === "confirm" ? "confirmed" : "rejected";
      await onAdjudicated(f.finding_id, nextStatus);
      setItemMsg({
        ok: true,
        text: `已${decision === "confirm" ? "确认" : "驳回"} ${f.finding_id}`,
      });
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
      setItemMsg({ ok: false, text: `裁决失败（${msg}）` });
    } finally {
      setBusy(null);
    }
  };

  return (
    <li
      id={`evidence-item-${f.finding_id}`}
      className={
        "evidence__item" + (isActive ? " evidence__item--active" : "")
      }
    >
      <div className="evidence__head">
        <span className="font-data">
          <strong>
            {index + 1}. {f.control_code}
          </strong>
        </span>
        <span className="font-data hint">{f.finding_id}</span>
        <StatusBadge axis="severity" value={f.severity} />
        <span className="hint" data-finding-status={effectiveStatus}>
          {effectiveStatus === "candidate"
            ? "候选（待裁）"
            : effectiveStatus === "confirmed"
              ? "已确认"
              : effectiveStatus === "rejected"
                ? "已驳回"
                : effectiveStatus}
        </span>
        {quote && (
          <Button
            variant="ghost"
            className="evidence__locate-btn"
            onClick={() => onLocate(f.finding_id)}
          >
            定位原文
          </Button>
        )}
      </div>

      {quote === null || quote === undefined ? (
        <div className="evidence__quote evidence__quote--empty">无原文引用</div>
      ) : (
        <div
          className={
            "evidence__quote" + (isLong ? " evidence__quote--long" : "")
          }
          onClick={() => onLocate(f.finding_id)}
        >
          {quote}
        </div>
      )}

      <div className="evidence__why">
        <span>
          规则依据：{(f.authority_ref ?? []).map((r) => r.ref_id).join("、") || "未登记"}{" "}
          <span className={authInfo.cls} data-status-badge="">
            {authInfo.text}
          </span>
        </span>
      </div>

      {f.rule_conflict && (
        <div className="state state--warn">
          <strong>规则依据冲突</strong>
          ：该项涉及两条相互冲突的规则依据，<strong>需人工裁定</strong>。
          {f.resolution_detail?.reason ? `（${f.resolution_detail.reason}）` : ""}
          {conflictRefs.length > 0 && (
            <div className="conflict-grid">
              {conflictRefs.map((ref, idx) => (
                <div key={idx} className="conflict-card">
                  依据 {idx + 1}：<span className="font-data">{String(ref.ref_id ?? "未命名")}</span>
                  （{ref.state === "ok" ? "有效" : String(ref.state ?? "待核")}）
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 证据链卡片内就地裁决（G-07 / 修 D-08） */}
      {(effectiveStatus === "candidate" || itemMsg !== null) && (
        <div className="evidence__adjudicate" data-finding-adjudicate={f.finding_id}>
          {effectiveStatus === "candidate" && (
            <div className="actions__row">
              <Button
                variant="secondary"
                disabled={!canAdjudicate || busy !== null}
                onClick={() => void handleAdjudicate("confirm")}
              >
                确认违规
              </Button>
              <Button
                variant="secondary"
                disabled={!canAdjudicate || busy !== null}
                onClick={() => void handleAdjudicate("reject")}
              >
                驳回候选
              </Button>
              <Button
                variant="ghost"
                onClick={() => setShowReason(!showReason)}
              >
                {showReason ? "收起单条理由" : "附裁决理由"}
              </Button>
              {!canAdjudicate && (
                <span className="hint">（认领案件后可就地裁决）</span>
              )}
            </div>
          )}
          {showReason && effectiveStatus === "candidate" && (
            <div className="evidence__reason-box">
              <label htmlFor={`finding-reason-${f.finding_id}`} className="hint">
                单条裁决理由（{f.finding_id}）
              </label>
              <input
                id={`finding-reason-${f.finding_id}`}
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="输入确认或驳回该条候选的具体依据…"
              />
            </div>
          )}
          {itemMsg && (
            <p className={itemMsg.ok ? "hint" : "error"} role="status">
              {itemMsg.text}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

function NotEvaluatedList({ items }: { items: NotEvaluated[] }) {
  if (items.length === 0) {
    return <p className="hint">全部适用规则项均已核查。</p>;
  }
  return (
    <ul className="notrun">
      {items.map((it, i) => (
        <li key={i}>
          <span>{it.what ?? "未命名规则项"}</span>
          <span className="notrun__why">
            {it.label ?? WHY_TEXT[String(it.why)] ?? String(it.why ?? "未说明")}
          </span>
        </li>
      ))}
    </ul>
  );
}

export interface CaseDetailViewProps {
  embeddedCaseId?: string;
}

export default function CaseDetailPage({ embeddedCaseId }: CaseDetailViewProps = {}) {
  const params = useParams<{ caseId: string }>();
  const caseId = embeddedCaseId ?? params.caseId;
  const isEmbedded = Boolean(embeddedCaseId);
  const { devEnabled, current, sessionEpoch } = useIdentity();
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);
  const [localFindingStatuses, setLocalFindingStatuses] = useState<
    Record<string, "confirmed" | "rejected">
  >({});
  const [disputeCount, setDisputeCount] = useState(0);

  useEffect(() => {
    if (!__REVIEW_DEV_IDENTITY__) return;
    let alive = true;
    import("../data/taxonomyInternal").then((m) => {
      if (alive) setDisputeCount(m.boundaryDisputes.length);
    });
    return () => {
      alive = false;
    };
  }, []);
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
    setActiveFindingId(null);
    setLocalFindingStatuses({});
    if (!devEnabled || current !== null) void load();
  }, [caseId, current, devEnabled, load, sessionEpoch]);

  const handleLocateFinding = useCallback((findingId: string) => {
    setActiveFindingId(findingId);
    const markEl = document.getElementById(`unit-mark-${findingId}`);
    if (markEl) {
      markEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, []);

  const handleSelectFromUnit = useCallback((findingId: string) => {
    setActiveFindingId(findingId);
    const itemEl = document.getElementById(`evidence-item-${findingId}`);
    if (itemEl) {
      itemEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, []);

  const TitleTag = isEmbedded ? "h2" : "h1";

  if (error) {
    const head =
      error.status === 403
        ? "无权读取该案件"
        : error.status === 404
          ? "案件不存在"
          : "读取失败";
    return (
      <section className="case">
        <TitleTag>案件详情</TitleTag>
        <div
          className={
            "state " +
            (error.status === 403 || error.status === 404
              ? "state--forbidden"
              : "state--error")
          }
          role="alert"
        >
          <h2>{head}</h2>
          <p>
            {error.status === 403
              ? "当前身份不在该案件的可见范围内（tenant + product_line + assigned/actionable）。"
              : error.message}
          </p>
        </div>
        {!isEmbedded && (
          <p>
            <Link to="/queue">
              <Icon name="arrow-left" size={12} /> 返回复核队列
            </Link>
          </p>
        )}
      </section>
    );
  }

  if (!detail) {
    return (
      <section className="case">
        <TitleTag>案件详情</TitleTag>
        <p className="hint">加载中…</p>
      </section>
    );
  }

  const ir = detail.ir;
  const dec = ir.decision;
  const cov = ir.coverage;
  const covBadge = resolveCoverageBadge(cov.coverage_state);
  const notEvaluated = cov.not_evaluated_reason ?? [];
  const review = detail.review;
  const leaseActive =
    typeof review?.lease_expires === "number" &&
    review.lease_expires > Date.now() / 1000;
  const canAdjudicate =
    current !== null &&
    review?.status === "claimed" &&
    review.assignee === current.id &&
    leaseActive;

  return (
    <section className={isEmbedded ? "case case--embedded" : "case case--dual"}>
      <div className="case__top-bar">
        <div className="case__head">
          <TitleTag>{isEmbedded ? `正在查看 ${detail.case_id}` : "案件详情"}</TitleTag>
          <StatusBadge axis="decision" value={dec.state} />
          <span className="font-data">{detail.case_id}</span>
          {isEmbedded && (
            <Link
              to={`/cases/${encodeURIComponent(detail.case_id)}`}
              className="btn"
            >
              单独打开这一页 <Icon name="arrow-up-right" size={11} />
            </Link>
          )}
        </div>
        <p className="case__sub">
          审查单 <span className="font-data">{ir.ir_id}</span>
          {ir.created_at && <>，提交于 {ir.created_at}</>}
        </p>
        <InlineMetricSummary
          scope="case"
          countsLabel={`查出问题 ${(ir.findings ?? []).length} 处，未查 ${notEvaluated.length} 项`}
          trendLabel={null}
          untestedLabel={notEvaluated.length > 0 ? "partial" : cov.coverage_state}
        />
      </div>

      <div className="case__workspace">
        {/* 左栏：ContentUnit 待审原件与覆盖边界高亮联动（G-02） */}
        <ContentUnitViewer
          unit={detail.content_unit}
          unitRef={ir.content_unit_ref}
          findings={ir.findings ?? []}
          activeFindingId={activeFindingId}
          onSelectFinding={handleSelectFromUnit}
          observations={detail.multimodal_observations}
          observationNote={detail.multimodal_note}
        />

        {/* 右栏：判定、覆盖证明、证据链就地裁决与复核动作台账 */}
        <div className="case__inspector">
          <h2>判定</h2>
          <dl className="facts">
            <dt>对外标签</dt>
            <dd>
              <StatusBadge axis="decision" value={dec.state} />{" "}
              <span className="hint">（系统初审结论）</span>
            </dd>
            <dt>放行状态</dt>
            <dd>
              <span className="facts__inline-row">
                <strong>{dec.release_status}</strong>
                <span className="hint">（须经合规签发确认后放行）</span>
                <Link
                  to={`/release/${encodeURIComponent(detail.case_id)}`}
                  className="btn"
                >
                  前往合规签发 <Icon name="arrow-up-right" size={11} />
                </Link>
              </span>
            </dd>
            <dt>并行义务</dt>
            <dd>{(dec.obligations ?? []).join("、") || "无"}</dd>
          </dl>

          <h2>覆盖证明</h2>
          <dl className="facts">
            <dt>覆盖状态</dt>
            <dd>
              <StatusBadge axis="coverage" value={cov.coverage_state} />
              {covBadge.isPartial && <strong> 仅已覆盖部分可判</strong>}
            </dd>
            <dt>已核查类型</dt>
            <dd>{(cov.modalities_evaluated ?? []).map((m) => ({ free_text: "文本", product_listing: "商品页", image: "图片", video: "视频" }[m] ?? m)).join("、") || "未测"}</dd>
            <dt>适用规则项</dt>
            <dd className="font-data">
              {(cov.control_points_applied ?? []).join("、") || "无"}
            </dd>
            <dt>规则版本</dt>
            <dd className="font-data">
              {cov.rules_version ? (
                cov.rules_version.length > 24 ? (
                  // rules_version 可能是完整 JSON（指纹 + 版本）：界面只表态「已登记」，
                  // 完整值收进展开区供对账 —— 一长串哈希不是审核员要读的信息。
                  <details className="facts__detail">
                    <summary>已登记</summary>
                    <code>{cov.rules_version}</code>
                  </details>
                ) : (
                  cov.rules_version
                )
              ) : (
                "未测"
              )}
            </dd>
            <dt>分类规范</dt>
            <dd className="spec-version">
              {/* ★ 断言 A9：spec_version 与 spec_fingerprint 必须同时出现 */}
              <span>按 spec {meta.spec_version ?? "未测"}</span>
              <span className="font-data">{meta.spec_fingerprint ?? "未测"}</span>
            </dd>
          </dl>

          <h2>未评估的部分</h2>
          <NotEvaluatedList items={notEvaluated} />

          <h2>证据链</h2>
          <SpecSeamNote disputeCount={disputeCount} />
          {(ir.findings ?? []).length === 0 ? (
            <p className="hint">未发现违规或风险项。</p>
          ) : (
            <ol className="evidence">
              {(ir.findings ?? []).map((f, i) => (
                <EvidenceItem
                  key={f.finding_id}
                  f={f}
                  index={i}
                  isActive={activeFindingId === f.finding_id}
                  canAdjudicate={canAdjudicate}
                  caseId={detail.case_id}
                  version={review?.version ?? null}
                  adjudicatedStatus={localFindingStatuses[f.finding_id]}
                  onLocate={handleLocateFinding}
                  onAdjudicated={async (fid, nextSt) => {
                    setLocalFindingStatuses((prev) => ({
                      ...prev,
                      [fid]: nextSt,
                    }));
                    return refreshAfterWrite();
                  }}
                />
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
                  <Link to={`/reports/${encodeURIComponent(r.report_id)}`}>
                    {r.report_id}
                  </Link>
                  {r.published_at ? `，${r.published_at}` : ""}
                </li>
              ))}
            </ul>
          )}

          <div className="actions" data-action-bar="">
            <h2>复核动作</h2>
            <dl className="facts">
              <dt>处理状态</dt>
              <dd>{({ unassigned: "待认领", claimed: "处理中", submitted: "已提交结论" } as Record<string, string>)[review?.status ?? ""] ?? review?.status ?? "待认领"}</dd>
              <dt>当前负责人</dt>
              <dd>{review?.assignee ?? "未认领"}</dd>
              {review?.lease_expires ? (
                <>
                  <dt>锁定有效期</dt>
                  <dd>
                    {`${leaseActive ? "有效至" : "已过期于"} ${new Date(review.lease_expires * 1000).toLocaleString()}`}
                  </dd>
                </>
              ) : null}
            </dl>
            {__REVIEW_DEV_IDENTITY__ ? (
              __REVIEW_WRITE_ENABLED__ && DevReviewActions ? (
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
              ) : null
            ) : (
              <ReviewActions detail={detail} refresh={refreshAfterWrite} />
            )}
            <p className="actions__note">
              {__REVIEW_DEV_IDENTITY__
                ? current
                  ? `当前开发身份：${current.label}（${current.id}）。人工意见不改变机器标签或放行状态。`
                  : "当前没有开发 session；页面保持只读。"
                : "生产：登录后可认领、存草稿、提交与逐条裁决；人工意见不改变机器标签或放行状态。"}
            </p>
          </div>

          {!isEmbedded && (
            <p>
              <Link to="/queue">
                <Icon name="arrow-left" size={12} /> 返回复核队列
              </Link>
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
