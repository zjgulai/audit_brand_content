import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ApiError,
  appOrigin,
  reviewApi,
  type CaseDetail,
  type CaseSummary,
} from "../api/client";
import {
  releaseClient,
  type ReleasePendingItem,
  type ReleaseReadiness,
} from "../api/release-client";
import { useIdentity } from "../components/IdentitySwitcher";
import StatusBadge from "../components/StatusBadge";
import Button from "../ui/Button";
import Icon from "../ui/icon";

/**
 * 签发中心 G-1（P-07 · Wave D 落 G-05 决策，覆盖 `/release` 与 `/release/:caseId`）。
 *
 * 1. 待签发列表（`/release`）：
 *    展示待放行案件，并对提交人本人（self_submission）或最终复核人本人（self_review）
 *    显式标注 SoD 职责分离限制。
 * 2. 专属签发核验台（`/release/:caseId`）：
 *    - 区块一：四前置与处置义务就绪度核验（消费 `GET /api/v1/cases/{id}/release-readiness`）；
 *    - 区块二：18 项不可变签名绑定清单（Signature Binding Inspector，SB-1…SB-11）与五类自动失效输入声明；
 *    - 区块三：飞书 SSO Step-Up 重新认证（5 分钟有效期、单次使用、绑定 principal+case+action+nonce）
 *      + 必填理由 → 调用 `releaseClient.decide` / `releaseClient.revoke`。
 */
export default function ReleasePage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { devEnabled, current, sessionEpoch } = useIdentity();

  const [pendingRows, setPendingRows] = useState<ReleasePendingItem[]>([]);
  const [fallbackCases, setFallbackCases] = useState<CaseSummary[]>([]);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [readiness, setReadiness] = useState<ReleaseReadiness | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [actionMode, setActionMode] = useState<"sign" | "reject" | "revoke">(
    "sign",
  );
  const [reason, setReason] = useState<string>("");
  const [stepUpToken, setStepUpToken] = useState<string>("");
  const [nonce, setNonce] = useState<string>(() =>
    `nonce-${crypto.randomUUID().slice(0, 8)}`,
  );
  const [busy, setBusy] = useState<boolean>(false);
  const [resultMsg, setResultMsg] = useState<{
    ok: boolean;
    text: string;
  } | null>(null);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pending, allCases] = await Promise.all([
        releaseClient.listPending(),
        reviewApi.listCases(),
      ]);
      setPendingRows(Array.isArray(pending) ? pending : []);
      setFallbackCases(
        (allCases ?? []).filter((c) => c.release_status === "待放行"),
      );
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const [c, r] = await Promise.all([
        reviewApi.getCase(id),
        releaseClient.getReadiness(id),
      ]);
      setDetail(c);
      setReadiness(r);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (devEnabled && current === null) return;
    if (caseId) {
      void loadDetail(caseId);
    } else {
      void loadList();
    }
  }, [caseId, current, devEnabled, loadDetail, loadList, sessionEpoch]);

  const handleStartReauth = async () => {
    if (!caseId) return;
    setResultMsg(null);
    try {
      const res = await fetch(`${appOrigin}/auth/reauth/start`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: caseId,
          action: actionMode,
          nonce,
        }),
      });
      if (res.ok) {
        const data = (await res.json()) as { authorize_url?: string };
        if (data.authorize_url) {
          window.open(data.authorize_url, "_blank", "noopener,noreferrer");
          return;
        }
      }
      setResultMsg({
        ok: false,
        text: "当前环境未开启在线飞书 Step-Up 重定向（/auth/reauth/start）；可输入已签发的 step_up_token 进行核验。",
      });
    } catch {
      setResultMsg({
        ok: false,
        text: "无法连接 /auth/reauth/start；请在下方填入一次性 step_up_token。",
      });
    }
  };

  const handleSubmitRelease = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!caseId || !detail || busy) return;
    setBusy(true);
    setResultMsg(null);
    const version = detail.review?.version ?? 1;
    const key = crypto.randomUUID();
    try {
      if (actionMode === "revoke") {
        await releaseClient.revoke(caseId, {
          version,
          stepUpToken,
          nonce,
          reason,
          idempotencyKey: key,
        });
        setResultMsg({
          ok: true,
          text: `案件 ${caseId} 签发记录已撤回（revoked）。若内容已发布将自动生成下线任务。`,
        });
      } else {
        await releaseClient.decide(caseId, {
          decision: actionMode,
          version,
          stepUpToken,
          nonce,
          reason,
          idempotencyKey: key,
        });
        setResultMsg({
          ok: true,
          text: `案件 ${caseId} 已完成受控签发决策（${actionMode === "sign" ? "signed / 已放行" : "rejected / 已拒绝"}）。`,
        });
      }
      await loadDetail(caseId);
    } catch (cause: unknown) {
      if (cause instanceof ApiError) {
        setResultMsg({
          ok: false,
          text: `签发门拦截（HTTP ${cause.status}）：${cause.message}`,
        });
      } else {
        setResultMsg({
          ok: false,
          text: cause instanceof Error ? cause.message : String(cause),
        });
      }
    } finally {
      setBusy(false);
    }
  };

  if (!caseId) {
    const mergedList: Array<{
      case_id: string;
      state?: string | null;
      product_line?: string | null;
      release_status?: string | null;
      submitter_id?: string | null;
      final_reviewer_id?: string | null;
    }> =
      pendingRows.length > 0
        ? pendingRows
        : fallbackCases.map((c) => ({
            case_id: c.case_id,
            state: c.state,
            product_line: c.product_line,
            release_status: c.release_status,
            submitter_id: null,
            final_reviewer_id: c.assignee_id,
          }));

    return (
      <section className="cases-page" aria-labelledby="release-center-title">
        <div className="cases-page__head">
          <div>
            <h1 id="release-center-title">签发台 G-1（P-07）</h1>
            <p className="hint">
              全系统唯一允许改变 <code>release_status</code> 的受控入口。
              执行人级 allowlist + 租户/品线 scope + 职责分离（SoD：提交人与最终复核人不得自签）+ 飞书 SSO Step-Up 二次认证。
            </p>
          </div>
          <span className="font-data hint">
            待放行候选：{mergedList.length} 条
          </span>
        </div>

        {error && (
          <div className="state state--error" role="alert">
            读取待签发列表失败：{error}
          </div>
        )}

        {loading ? (
          <p className="hint">加载待签发队列中…</p>
        ) : mergedList.length === 0 ? (
          <div className="state">
            <p className="hint">当前没有处于「待放行」状态的案件。</p>
          </div>
        ) : (
          <div className="cases-table-wrap">
            <table className="cases-table">
              <thead>
                <tr>
                  <th scope="col">案件编号</th>
                  <th scope="col">审查标签</th>
                  <th scope="col">产品线</th>
                  <th scope="col">当前放行状态</th>
                  <th scope="col">SoD 职责分离预检</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                {mergedList.map((item) => {
                  const isSelfSub =
                    Boolean(current?.id) &&
                    item.submitter_id === current?.id;
                  const isSelfRev =
                    Boolean(current?.id) &&
                    item.final_reviewer_id === current?.id;
                  const sodBlocked = isSelfSub || isSelfRev;
                  return (
                    <tr key={item.case_id}>
                      <td className="font-data">
                        <Link
                          to={`/release/${encodeURIComponent(item.case_id)}`}
                        >
                          {item.case_id}
                        </Link>
                      </td>
                      <td>
                        <StatusBadge axis="decision" value={item.state} />
                      </td>
                      <td>{item.product_line ?? "未测"}</td>
                      <td>{item.release_status ?? "待放行"}</td>
                      <td>
                        {sodBlocked ? (
                          <span
                            className="badge badge--warn"
                            data-status-badge=""
                          >
                            SoD 限制：
                            {isSelfSub
                              ? "本人提交 (self_submission)"
                              : "本人复核 (self_review)"}
                          </span>
                        ) : (
                          <span
                            className="badge badge--pass"
                            data-status-badge=""
                          >
                            SoD 可签核
                          </span>
                        )}
                      </td>
                      <td>
                        <Link
                          to={`/release/${encodeURIComponent(item.case_id)}`}
                          className="btn"
                        >
                          进入签发核验台 <Icon name="arrow-up-right" size={11} />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    );
  }

  const ir = detail?.ir;
  const unit = detail?.content_unit;
  const isSelfReview =
    Boolean(current?.id) && detail?.review?.assignee === current?.id;

  return (
    <section className="case case--dual" aria-labelledby="release-detail-title">
      <div className="case__head">
        <h1 id="release-detail-title">签发核验台 G-1</h1>
        <span className="font-data">{caseId}</span>
        {ir && <StatusBadge axis="decision" value={ir.decision.state} />}
        <Link to={`/cases/${encodeURIComponent(caseId)}`} className="btn">
          查看案件证据链
        </Link>
      </div>

      {error && (
        <div className="state state--error" role="alert">
          读取签发就绪度失败：{error}
        </div>
      )}

      {loading || !detail || !ir ? (
        <p className="hint">加载签发核验数据中…</p>
      ) : (
        <div className="case__workspace">
          {/* 左栏：四前置就绪度 + 18 项签名绑定清单（SB-1…SB-11） */}
          <div className="unit-pane">
            <h2>1. 四前置与处置义务就绪度（release-readiness）</h2>
            <dl className="facts">
              <dt>就绪状态</dt>
              <dd>
                <StatusBadge
                  axis="coverage"
                  value={readiness?.ready ? "full" : "partial"}
                />{" "}
                <span>
                  {readiness?.ready
                    ? "四前置全部满足"
                    : "需核对下方前置条件与人工理由"}
                </span>
              </dd>
              <dt>1. 审查记录完整</dt>
              <dd>IR {ir.ir_id} · 回执 {ir.receipt_ref ?? "未测"}</dd>
              <dt>2. 标签处置前置</dt>
              <dd>
                当前标签 <strong>{ir.decision.state}</strong> · 台账状态{" "}
                <code>{detail.review?.status ?? "unassigned"}</code>
              </dd>
              <dt>3. 并行义务与冲突</dt>
              <dd>
                义务：{(ir.decision.obligations ?? []).join("、") || "无"} ·
                未裁冲突：
                {(ir.findings ?? []).filter((f) => f.rule_conflict).length} 项
              </dd>
              <dt>4. 双指纹一致性</dt>
              <dd className="font-data">
                text_sha256={unit?.fingerprint?.text_sha256?.slice(0, 16) ?? "待核"}…
              </dd>
            </dl>

            <h2>2. 18 项不可变签名绑定清单（Signature Binding）</h2>
            <p className="hint">
              签发后以下任一已使用依据、规则/知识库快照或内容指纹发生变化，签名将自动转为{" "}
              <code>invalidated</code> 并入队全量重审（无人工 Override，IA-1…IA-3）。
            </p>
            <dl className="facts font-data">
              <dt>case_version</dt>
              <dd>{detail.review?.version ?? 0}</dd>
              <dt>ir_id / ir_version</dt>
              <dd>
                {ir.ir_id} / {ir.ir_version}
              </dd>
              <dt>raw_sha256</dt>
              <dd>{unit?.fingerprint?.raw_sha256 ?? "未内嵌"}</dd>
              <dt>text_sha256</dt>
              <dd>{unit?.fingerprint?.text_sha256 ?? "未内嵌"}</dd>
              <dt>rule_snapshot</dt>
              <dd>{ir.rule_snapshot ?? "未测"}</dd>
              <dt>kb_snapshot</dt>
              <dd>{ir.kb_snapshot ?? "未测"}</dd>
              <dt>control_points_ver</dt>
              <dd>{ir.control_points_version ?? "未测"}</dd>
              <dt>used_authority_refs</dt>
              <dd>
                {[
                  ...new Set(
                    (ir.findings ?? []).flatMap((f) =>
                      (f.authority_ref ?? []).map((r) => r.ref_id),
                    ),
                  ),
                ].join(", ") || "无"}
              </dd>
              <dt>media_root_hash</dt>
              <dd>RFC 8785 JCS SHA-256（后端 ReleaseGate 实时计算）</dd>
            </dl>
          </div>

          {/* 右栏：Step-Up 重新认证与签发/拒绝/撤回执行面板 */}
          <div className="case__inspector">
            <div className="actions">
              <h2>3. 飞书 SSO Step-Up 二次认证与受控签发</h2>
              {isSelfReview && (
                <div className="state state--warn" role="alert">
                  <strong>SoD 职责分离警告（self_review）</strong>：当前身份（
                  <code>{current?.id}</code>）是本案件的复核负责人，提交签发将被服务端{" "}
                  <code>ReleaseGate</code> 以 403 <code>SoDViolation</code> 拒绝。
                </div>
              )}

              {resultMsg && (
                <div
                  className={
                    "state " + (resultMsg.ok ? "" : "state--error")
                  }
                  role="alert"
                >
                  {resultMsg.text}
                </div>
              )}

              <form
                className="submit-form"
                onSubmit={(e) => void handleSubmitRelease(e)}
              >
                <div
                  className="verdict-picker"
                  role="group"
                  aria-label="选择签发动作"
                >
                  <label className="verdict-radio">
                    <input
                      type="radio"
                      name="release-action"
                      checked={actionMode === "sign"}
                      onChange={() => setActionMode("sign")}
                    />
                    <span>签发放行（sign → 已放行）</span>
                  </label>
                  <label className="verdict-radio">
                    <input
                      type="radio"
                      name="release-action"
                      checked={actionMode === "reject"}
                      onChange={() => setActionMode("reject")}
                    />
                    <span>拒绝放行（reject → 已拒绝）</span>
                  </label>
                  <label className="verdict-radio">
                    <input
                      type="radio"
                      name="release-action"
                      checked={actionMode === "revoke"}
                      onChange={() => setActionMode("revoke")}
                    />
                    <span>撤回历史签名（revoke → 已撤回）</span>
                  </label>
                </div>

                <div className="submit-field">
                  <label htmlFor="release-reason">
                    签发 / 拒绝 / 撤回书面理由（必填，记入不可变签名台账）
                  </label>
                  <textarea
                    id="release-reason"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="填写签发核准依据、豁免原因或撤回理由…"
                  />
                </div>

                <div className="submit-grid">
                  <div>
                    <label htmlFor="release-nonce">绑定随机挑战值（nonce）</label>
                    <input
                      id="release-nonce"
                      type="text"
                      className="font-data"
                      value={nonce}
                      onChange={(e) => setNonce(e.target.value)}
                    />
                  </div>
                  <div>
                    <label htmlFor="release-stepup">
                      一次性 Step-Up Token（TTL 5m，single-use）
                    </label>
                    <input
                      id="release-stepup"
                      type="text"
                      className="font-data"
                      value={stepUpToken}
                      onChange={(e) => setStepUpToken(e.target.value)}
                      placeholder="完成飞书二次认证后自动下发或粘贴…"
                    />
                  </div>
                </div>

                <div className="actions__row">
                  <Button
                    variant="secondary"
                    onClick={() => void handleStartReauth()}
                  >
                    <Icon name="user-check" size={12} /> 发起飞书 SSO Step-Up 重认证
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    data-risk-action="release-decision"
                    disabled={
                      busy ||
                      !reason.trim() ||
                      !stepUpToken.trim() ||
                      !nonce.trim()
                    }
                  >
                    {busy
                      ? "提交签发门核验中…"
                      : actionMode === "sign"
                        ? "确认签发放行"
                        : actionMode === "reject"
                          ? "确认拒绝放行"
                          : "确认撤回签名"}
                  </Button>
                </div>
              </form>
            </div>

            <p>
              <Link to="/release">
                <Icon name="arrow-left" size={12} /> 返回待签发列表
              </Link>
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
