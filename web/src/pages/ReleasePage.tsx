import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import LoadingRows from "../components/LoadingRows";
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
            // ★ ADR-0021 · W-2：改前这里是 `submitter_id: null` ——
            //   一个写死的 null 让 `isSelfSub` 恒 false，自签检查等于不存在。
            //   现在**不编值**：`undefined` 表示「这个数据源没有这个字段」，
            //   由下面的 `sodUnknown` 把它渲染成「未测（提交人未知）」。
            //
            //   ★ 为什么不是 null：`CaseSummary` 的 submitter 字段类型就是
            //     `string | null`，null 在正常路径上也会出现（真的没有提交人）。
            //     用 undefined 才能区分「没有这个字段」与「字段是 null」。
            submitter_id: undefined,
            final_reviewer_id: c.assignee_id,
          }));

    return (
      <section className="cases-page" aria-labelledby="release-center-title">
        <div className="cases-page__head">
          <div>
            <h1 id="release-center-title">合规签发</h1>
            <p className="hint">
              复核完成后在此正式签发放行。提交人与复核人本人不可自签。
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
          <LoadingRows rows={3} label="正在加载待签发队列" />
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
                  <th scope="col">签发资格</th>
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
                  // ★ ADR-0021 · W-2：提交人未知时不能装作「可签」。
                  //   判定口径：两条规则都读过、且**至少一条的数据缺失**
                  //   （undefined = 这个源没有这个字段；null = 字段确实是空）。
                  //   `submitter_id: undefined` 就是 fallback 分支标记「我不知道」的方式。
                  const sodUnknown =
                    !isSelfSub &&
                    !isSelfRev &&
                    (item.submitter_id === undefined ||
                      item.submitter_id === null ||
                      item.final_reviewer_id === undefined);
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
                        {/* ★ ADR-0021 · W-2：改前三元的两个分支文案完全相同
                            （`? "不可自签" : "不可自签"`），改一个分支不会有任何
                            可见变化 —— 那是死分支。
                            改前这里是一个 `sodBlocked = isSelfSub || isSelfRev` 的并集，但它
                            只拦不说是哪一条：**自签**（提交人签自己）与
                            **自审**（终审人签字）是两条不同的规则，
                            补救动作也不同（前者要换人签，后者要有第二审批）。
                            所以这里分开说。 */}
                        {isSelfSub ? (
                          <span className="badge badge--warn" data-status-badge="">
                            不可自签（本人提交）
                          </span>
                        ) : isSelfRev ? (
                          <span className="badge badge--warn" data-status-badge="">
                            不可自签（本人终审）
                          </span>
                        ) : sodUnknown ? (
                          /* ★ 「不知道能不能签」必须与「能签」长得不一样。
                             改前 submitter_id 被写死成 null，于是 isSelfSub 恒 false，
                             界面一律显示「可签发」—— 静默的合规失效。 */
                          <span className="badge badge--untested" data-status-badge="">
                            未测（提交人未知）
                          </span>
                        ) : (
                          <span
                            className="badge badge--pass"
                            data-status-badge=""
                          >
                            可签发
                          </span>
                        )}
                      </td>
                      <td>
                        <Link
                          to={`/release/${encodeURIComponent(item.case_id)}`}
                          className="btn"
                        >
                          进入签发核验 <Icon name="arrow-up-right" size={11} />
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
        <h1 id="release-detail-title">签发核验</h1>
        <span className="font-data">{caseId}</span>
        {ir && <StatusBadge axis="decision" value={ir.decision.state} />}
        <Link to={`/cases/${encodeURIComponent(caseId)}`} className="btn">
          查看案件详情
        </Link>
      </div>

      {error && (
        <div className="state state--error" role="alert">
          读取签发就绪度失败：{error}
        </div>
      )}

      {loading || !detail || !ir ? (
        <LoadingRows rows={2} rowHeight={28} label="正在加载签发核验数据" />
      ) : (
        <div className="case__workspace">
          {/* 左栏：四前置就绪度 + 18 项签名绑定清单（SB-1…SB-11） */}
          <div className="unit-pane">
            <h2>放行前置条件</h2>
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
              <dt>审查单号</dt>
              <dd className="font-data">{ir.ir_id}</dd>
              <dt>当前结论与状态</dt>
              <dd>
                <strong>{ir.decision.state}</strong>（{({ unassigned: "待认领", claimed: "处理中", submitted: "已提交结论" } as Record<string, string>)[detail.review?.status ?? ""] ?? detail.review?.status ?? "待认领"}）
              </dd>
              <dt>附加义务与待裁项</dt>
              <dd>
                义务：{(ir.decision.obligations ?? []).join("、") || "无"}；未裁冲突：
                {(ir.findings ?? []).filter((f) => f.rule_conflict).length} 项
              </dd>
              <dt>内容校验</dt>
              <dd className="font-data">
                {unit?.fingerprint?.text_sha256 ? `已校验（${unit.fingerprint.text_sha256.slice(0, 12)}…）` : "待核"}
              </dd>
            </dl>

            <h2>签发绑定存证</h2>
            <p className="hint">
              签发后若内容或所依据的规则发生变更，原签发自动失效并重新进入审查。
            </p>
            <dl className="facts">
              <dt>记录版本</dt>
              <dd className="font-data">{detail.review?.version ?? 0}</dd>
              <dt>审查单版本</dt>
              <dd className="font-data">
                {ir.ir_id}（{ir.ir_version}）
              </dd>
              <dt>引用依据</dt>
              <dd className="font-data">
                {[
                  ...new Set(
                    (ir.findings ?? []).flatMap((f) =>
                      (f.authority_ref ?? []).map((r) => r.ref_id),
                    ),
                  ),
                ].join("、") || "无"}
              </dd>
              <dt>规则与知识库版本</dt>
              <dd className="font-data">
                {ir.rule_snapshot ?? "未测"} / {ir.kb_snapshot ?? "未测"}
              </dd>
            </dl>
          </div>

          {/* 右栏：Step-Up 重新认证与签发/拒绝/撤回执行面板 */}
          <div className="case__inspector">
            <div className="actions">
              <h2>二次认证与签发确认</h2>
              {isSelfReview && (
                <div className="state state--warn" role="alert">
                  <strong>不可自签提醒</strong>：当前账号（
                  <code>{current?.id}</code>）是本案的复核负责人，须由其他授权签发人放行。
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
                    <span>准予放行</span>
                  </label>
                  <label className="verdict-radio">
                    <input
                      type="radio"
                      name="release-action"
                      checked={actionMode === "reject"}
                      onChange={() => setActionMode("reject")}
                    />
                    <span>不予放行</span>
                  </label>
                  <label className="verdict-radio">
                    <input
                      type="radio"
                      name="release-action"
                      checked={actionMode === "revoke"}
                      onChange={() => setActionMode("revoke")}
                    />
                    <span>撤回已放行签名</span>
                  </label>
                </div>

                <div className="submit-field">
                  <label htmlFor="release-reason">
                    签发意见或撤回理由（必填）
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
                    <label htmlFor="release-nonce">签发校验码</label>
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
                      二次认证口令（5 分钟内有效）
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
                    <Icon name="user-check" size={12} /> 飞书二次认证
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
