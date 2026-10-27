import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import LoadingRows from "../components/LoadingRows";
import { ApiError, request } from "../api/client";
import { useIdentity } from "../components/IdentitySwitcher";
import Button from "../ui/Button";
import FieldState from "../ui/FieldState";
import Icon from "../ui/icon";

/**
 * 下线任务台（P-08 · Wave D 落 UJ-5 与 TD-1…TD-21 / TF-1…TF-19）。
 *
 * 核心铁律（Invariant 6 & TD-8b）：
 *   1. 下线任务无硬 deadline（no_hard_deadline），但未完成任务**绝不显示绿色或相关“未超期/安全”字样**；
 *      一律持续展示任务年龄（天/小时）、提醒次数、积压与状态；
 *   2. 完成回填（complete）强制校验：platform + executed_by + executed_at（不得晚于当前）
 *      + 证据（receipt_id 或 result_url 或仓外 0700 截图引用）；
 *   3. 豁免（waive）强制双人独立审批：Approver 1 !== Approver 2 !== Executor，原签发人不得唯一（TF-10…TF-14）。
 */

export interface TakedownTaskItem {
  task_id: string;
  case_id: string;
  platform: string;
  tenant?: string;
  product_line?: string;
  assignee?: string | null;
  state: "pending" | "in_progress" | "completed" | "failed" | "waived" | string;
  created_at?: string;
  reminder_count?: number;
  last_reminded_at?: string | null;
  version?: number;
  evidence?: Record<string, unknown> | null;
  waived?: Record<string, unknown> | null;
}

// T-312d：任务年龄只有一个口径 —— 后端 metrics_view（北京日期）算好随列表
// 下发，前端只做**格式化**（天/小时）；客户端时钟不参与年龄计算
// （跨时区/跨零点会给出与后端不同但仍"看起来对"的答案）。
function formatAgeDays(ageDays: number | undefined): string {
  if (ageDays === undefined || ageDays === null || Number.isNaN(ageDays)) {
    return "年龄未测（后端未给出 age_days）";
  }
  const totalHours = Math.max(0, Math.floor(ageDays * 24));
  const days = Math.floor(totalHours / 24);
  const remHours = totalHours % 24;
  return `已持续 ${days} 天 ${remHours} 小时，无硬期限，持续追踪`;
}

export default function TakedownPage() {
  const { devEnabled, current, sessionEpoch } = useIdentity();
  const [tasks, setTasks] = useState<TakedownTaskItem[] | null>(null);
  const [ageByTask, setAgeByTask] = useState<Map<string, number>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ ok: boolean; text: string } | null>(
    null,
  );
  const [busy, setBusy] = useState<boolean>(false);

  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [modalKind, setModalKind] = useState<
    "complete" | "waive" | "reassign" | null
  >(null);

  // 回填表单状态
  const [evPlatform, setEvPlatform] = useState<string>("amazon");
  const [evExecutedBy, setEvExecutedBy] = useState<string>("");
  const [evExecutedAt, setEvExecutedAt] = useState<string>(() =>
    new Date().toISOString().slice(0, 19) + "Z",
  );
  const [evReceiptId, setEvReceiptId] = useState<string>("");
  const [evResultUrl, setEvResultUrl] = useState<string>("");

  // 双人审批豁免状态
  const [approver1, setApprover1] = useState<string>("");
  const [approver2, setApprover2] = useState<string>("");
  const [waiveReason, setWaiveReason] = useState<string>("");
  const [waiveEvidence, setWaiveEvidence] = useState<string>("");

  // 改派状态
  const [newAssignee, setNewAssignee] = useState<string>("");

  const loadTasks = useCallback(async () => {
    try {
      // T-312d：响应形状 {tasks, metrics}；年龄一律读 metrics.ages。
      const data = await request<{
        tasks: TakedownTaskItem[];
        metrics: { ages: { task_id: string; age_days: number }[] };
      }>("/takedown-tasks");
      const list = Array.isArray(data?.tasks) ? data.tasks : [];
      setTasks(list);
      setAgeByTask(new Map(
        (data?.metrics?.ages ?? []).map((a) => [a.task_id, a.age_days]),
      ));
      setError(null);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message ?? String(e));
    }
  }, []);

  useEffect(() => {
    if (devEnabled && current === null) {
      setTasks(null);
      return;
    }
    void loadTasks();
  }, [current, devEnabled, loadTasks, sessionEpoch]);

  const runTransition = async (
    taskId: string,
    action: "start" | "fail" | "retry",
  ) => {
    if (busy) return;
    setBusy(true);
    setFlash(null);
    try {
      const updated = await request<TakedownTaskItem>(
        `/takedown-tasks/${encodeURIComponent(taskId)}/${action}`,
        {
          method: "POST",
          body: {},
          idempotencyKey: crypto.randomUUID(),
        },
      );
      setTasks((prev) =>
        (prev ?? []).map((t) => (t.task_id === taskId ? updated : t)),
      );
      setFlash({
        ok: true,
        text: `下线任务 ${taskId} 已执行 ${action} → 当前状态：${updated.state}`,
      });
    } catch (cause: unknown) {
      const msg =
        cause instanceof ApiError
          ? `HTTP ${cause.status}: ${cause.message}`
          : String(cause);
      setFlash({ ok: false, text: `任务动作未完成：${msg}` });
    } finally {
      setBusy(false);
    }
  };

  const handleCompleteSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!activeTaskId || busy) return;
    setBusy(true);
    setFlash(null);
    try {
      const updated = await request<TakedownTaskItem>(
        `/takedown-tasks/${encodeURIComponent(activeTaskId)}/complete`,
        {
          method: "POST",
          body: {
            evidence: {
              platform: evPlatform.trim(),
              executed_by: evExecutedBy.trim() || current?.id || "",
              executed_at: evExecutedAt.trim(),
              ...(evReceiptId.trim() ? { receipt_id: evReceiptId.trim() } : {}),
              ...(evResultUrl.trim() ? { result_url: evResultUrl.trim() } : {}),
            },
          },
          idempotencyKey: crypto.randomUUID(),
        },
      );
      setTasks((prev) =>
        (prev ?? []).map((t) => (t.task_id === activeTaskId ? updated : t)),
      );
      setModalKind(null);
      setFlash({
        ok: true,
        text: `下线任务 ${activeTaskId} 已完成证据回填并结案（completed，停止每日提醒）。`,
      });
    } catch (cause: unknown) {
      const msg =
        cause instanceof ApiError
          ? `HTTP ${cause.status}: ${cause.message}`
          : String(cause);
      setFlash({ ok: false, text: `回填校验未通过：${msg}` });
    } finally {
      setBusy(false);
    }
  };

  const handleWaiveSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!activeTaskId || busy) return;
    setBusy(true);
    setFlash(null);
    try {
      const updated = await request<TakedownTaskItem>(
        `/takedown-tasks/${encodeURIComponent(activeTaskId)}/waive`,
        {
          method: "POST",
          body: {
            approvers: [
              {
                actor: approver1.trim(),
                scopes: ["takedown.waive"],
                scope_match: true,
              },
              {
                actor: approver2.trim(),
                scopes: ["takedown.waive"],
                scope_match: true,
              },
            ],
            reason: waiveReason.trim(),
            evidence: { note: waiveEvidence.trim() },
          },
          idempotencyKey: crypto.randomUUID(),
        },
      );
      setTasks((prev) =>
        (prev ?? []).map((t) => (t.task_id === activeTaskId ? updated : t)),
      );
      setModalKind(null);
      setFlash({
        ok: true,
        text: `下线任务 ${activeTaskId} 已通过双人独立审批豁免（waived）。`,
      });
    } catch (cause: unknown) {
      const msg =
        cause instanceof ApiError
          ? `HTTP ${cause.status}: ${cause.message}`
          : String(cause);
      setFlash({ ok: false, text: `双人豁免校验拒绝：${msg}` });
    } finally {
      setBusy(false);
    }
  };

  const handleReassignSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!activeTaskId || !newAssignee.trim() || busy) return;
    setBusy(true);
    setFlash(null);
    try {
      const updated = await request<TakedownTaskItem>(
        `/takedown-tasks/${encodeURIComponent(activeTaskId)}/reassign`,
        {
          method: "POST",
          body: { assignee: newAssignee.trim() },
          idempotencyKey: crypto.randomUUID(),
        },
      );
      setTasks((prev) =>
        (prev ?? []).map((t) => (t.task_id === activeTaskId ? updated : t)),
      );
      setModalKind(null);
      setFlash({
        ok: true,
        text: `下线任务 ${activeTaskId} 已改派给 ${newAssignee.trim()}。`,
      });
    } catch (cause: unknown) {
      const msg =
        cause instanceof ApiError
          ? `HTTP ${cause.status}: ${cause.message}`
          : String(cause);
      setFlash({ ok: false, text: `改派被拒绝：${msg}` });
    } finally {
      setBusy(false);
    }
  };

  const renderTaskBadge = (state: string) => {
    // ★ TD-8b 铁律：未完成任务（pending / in_progress / failed）绝不使用 badge--pass 绿色
    if (state === "completed") {
      return (
        <span className="badge badge--pass" data-status-badge="">
          completed（已回填结案）
        </span>
      );
    }
    if (state === "failed") {
      return (
        <span className="badge badge--block" data-status-badge="">
          failed（下线失败，已升级统筹与法务）
        </span>
      );
    }
    if (state === "waived") {
      return (
        <span className="badge badge--sample" data-status-badge="">
          waived（双人审批豁免）
        </span>
      );
    }
    return (
      <span className="badge badge--warn" data-status-badge="">
        {state}（待下线积压）
      </span>
    );
  };

  return (
    <section className="cases-page" aria-labelledby="takedown-page-title">
      <div className="cases-page__head">
        <div>
          <h1 id="takedown-page-title">违规下架</h1>
          <p className="hint">
            已发布内容被撤回或规则更新失效后，在此跟踪各渠道下架进度并回填凭证。
          </p>
        </div>
        <span className="font-data hint">
          积压与历史任务：
          {tasks === null ? "尚未读取" : `${tasks.length} 项`}
        </span>
      </div>

      {error && (
        <div className="state state--error" role="alert">
          读取下线任务失败：{error}
        </div>
      )}

      {flash && (
        <div
          className={"state " + (flash.ok ? "" : "state--error")}
          role="status"
        >
          {flash.text}
        </div>
      )}

      {modalKind === "complete" && activeTaskId && (
        <div className="actions" role="dialog" aria-label="完成下线证据回填">
          <h2>完成下线证据回填</h2>
          <p className="hint">
            请填写下架平台、执行人与执行时间，并提供平台回执单号或核验链接。
          </p>
          <form
            className="submit-form"
            onSubmit={(e) => void handleCompleteSubmit(e)}
          >
            <div className="submit-grid">
              <div>
                <label htmlFor="td-ev-platform">下架平台</label>
                <input
                  id="td-ev-platform"
                  type="text"
                  value={evPlatform}
                  onChange={(e) => setEvPlatform(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="td-ev-by">执行人</label>
                <input
                  id="td-ev-by"
                  type="text"
                  value={evExecutedBy}
                  onChange={(e) => setEvExecutedBy(e.target.value)}
                  placeholder={current?.id ?? "输入执行人账号"}
                />
              </div>
              <div>
                <label htmlFor="td-ev-at">执行时间</label>
                <input
                  id="td-ev-at"
                  type="text"
                  className="font-data"
                  value={evExecutedAt}
                  onChange={(e) => setEvExecutedAt(e.target.value)}
                />
              </div>
            </div>
            <div className="submit-grid">
              <div>
                <label htmlFor="td-ev-receipt">
                  平台下架回执单号（与链接二选一）
                </label>
                <input
                  id="td-ev-receipt"
                  type="text"
                  className="font-data"
                  value={evReceiptId}
                  onChange={(e) => setEvReceiptId(e.target.value)}
                  placeholder="例如 AMZ-RM-99281"
                />
              </div>
              <div>
                <label htmlFor="td-ev-url">
                  下架核验链接
                </label>
                <input
                  id="td-ev-url"
                  type="text"
                  value={evResultUrl}
                  onChange={(e) => setEvResultUrl(e.target.value)}
                  placeholder="https://..."
                />
              </div>
            </div>
            <div className="actions__row">
              <Button
                type="submit"
                variant="secondary"
                disabled={
                  busy ||
                  !evPlatform.trim() ||
                  (!evReceiptId.trim() && !evResultUrl.trim())
                }
              >
                提交回填并结案
              </Button>
              <Button variant="ghost" onClick={() => setModalKind(null)}>
                取消
              </Button>
            </div>
          </form>
        </div>
      )}

      {modalKind === "waive" && activeTaskId && (
        <div className="actions" role="dialog" aria-label="双人独立审批豁免下线">
          <h2>双人独立审批豁免 {activeTaskId}</h2>
          <p className="hint">
            需两名不同的授权审批人共同确认；执行人本人不可自批。
          </p>
          <form
            className="submit-form"
            onSubmit={(e) => void handleWaiveSubmit(e)}
          >
            <div className="submit-grid">
              <div>
                <label htmlFor="td-waive-a1">第一审批人</label>
                <input
                  id="td-waive-a1"
                  type="text"
                  value={approver1}
                  onChange={(e) => setApprover1(e.target.value)}
                  placeholder="例如 u_legal_1"
                />
              </div>
              <div>
                <label htmlFor="td-waive-a2">
                  第二审批人
                </label>
                <input
                  id="td-waive-a2"
                  type="text"
                  value={approver2}
                  onChange={(e) => setApprover2(e.target.value)}
                  placeholder="例如 u_coord_1"
                />
              </div>
            </div>
            <div className="submit-grid">
              <div>
                <label htmlFor="td-waive-reason">豁免书面理由（必填）</label>
                <input
                  id="td-waive-reason"
                  type="text"
                  value={waiveReason}
                  onChange={(e) => setWaiveReason(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="td-waive-ev">豁免补充证据说明（必填）</label>
                <input
                  id="td-waive-ev"
                  type="text"
                  value={waiveEvidence}
                  onChange={(e) => setWaiveEvidence(e.target.value)}
                />
              </div>
            </div>
            <div className="actions__row">
              <Button
                type="submit"
                variant="secondary"
                disabled={
                  busy ||
                  !approver1.trim() ||
                  !approver2.trim() ||
                  approver1.trim() === approver2.trim() ||
                  !waiveReason.trim() ||
                  !waiveEvidence.trim()
                }
              >
                提交双人豁免审批
              </Button>
              <Button variant="ghost" onClick={() => setModalKind(null)}>
                取消
              </Button>
            </div>
          </form>
        </div>
      )}

      {modalKind === "reassign" && activeTaskId && (
        <div className="actions" role="dialog" aria-label="改派下线任务负责人">
          <h2>改派下线任务 {activeTaskId}</h2>
          <form
            className="submit-form"
            onSubmit={(e) => void handleReassignSubmit(e)}
          >
            <div className="submit-field">
              <label htmlFor="td-reassign-to">新执行负责人</label>
              <input
                id="td-reassign-to"
                type="text"
                value={newAssignee}
                onChange={(e) => setNewAssignee(e.target.value)}
                placeholder="输入新负责人 ID…"
              />
            </div>
            <div className="actions__row">
              <Button
                type="submit"
                variant="secondary"
                disabled={busy || !newAssignee.trim()}
              >
                确认改派
              </Button>
              <Button variant="ghost" onClick={() => setModalKind(null)}>
                取消
              </Button>
            </div>
          </form>
        </div>
      )}

      {tasks === null ? (
        <LoadingRows rows={3} label="正在加载下线任务" />
      ) : tasks.length === 0 ? (
        <div className="empty">
          <p className="empty__title">当前租户没有待执行的下线任务</p>
          <p>
            下线任务由签发撤回（revoke）或自动失效（invalidated）后自动生成，
            无需手工建单。此处为空表示没有已发布内容待下线。
          </p>
        </div>
      ) : (
        <ul className="handoff-list" data-takedown-list="">
          {tasks.map((t) => (
            <li key={t.task_id} className="state" data-takedown-task={t.task_id}>
              <div className="evidence__head">
                <span className="font-data">
                  <strong>{t.task_id}</strong>
                </span>
                {renderTaskBadge(t.state)}
                <span className="font-data hint">
                  {/* ★ ADR-0021 · W-2：`tenant ?? "t1"` 已去掉。
                      改前缺租户显示 "t1" —— 而 `t1` 是**真实的租户号格式**，
                      于是「不知道属于哪个租户」被显示成「属于 t1」。
                      这类兜底比留空更糟：它给出的不是一个占位符，是一个具体答案。 */}
                  范围：{t.platform}{" "}
                  <FieldState
                    value={t.tenant}
                    emptyText="租户未测"
                    missingReason="后端未返回 tenant"
                  />{" "}
                  {t.product_line ?? "未测"}
                </span>
              </div>

              <dl className="facts">
                <dt>关联案件</dt>
                <dd className="font-data">
                  <Link to={`/cases/${encodeURIComponent(t.case_id)}`}>
                    {t.case_id}
                  </Link>
                </dd>
                <dt>执行负责人</dt>
                <dd className="font-data">{t.assignee ?? "未指派（默认投放侧）"}</dd>
                <dt>开单时长与提醒</dt>
                <dd className="font-data" data-takedown-age="">
                  <Icon name="clock" size={11} /> {formatAgeDays(ageByTask.get(t.task_id))}
                  ，已提醒 {t.reminder_count ?? 0} 次
                </dd>
              </dl>

              <div className="actions__row">
                {t.state === "pending" && (
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => void runTransition(t.task_id, "start")}
                  >
                    开始执行
                  </Button>
                )}
                {t.state === "in_progress" && (
                  <>
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onClick={() => {
                        setActiveTaskId(t.task_id);
                        setEvPlatform(t.platform || "amazon");
                        setModalKind("complete");
                      }}
                    >
                      完成并回填证据
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onClick={() => void runTransition(t.task_id, "fail")}
                    >
                      标记下架失败
                    </Button>
                  </>
                )}
                {t.state === "failed" && (
                  <>
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onClick={() => void runTransition(t.task_id, "retry")}
                    >
                      重新尝试
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onClick={() => {
                        setActiveTaskId(t.task_id);
                        setModalKind("waive");
                      }}
                    >
                      申请豁免
                    </Button>
                  </>
                )}
                {t.state !== "completed" && t.state !== "waived" && (
                  <Button
                    variant="ghost"
                    disabled={busy}
                    onClick={() => {
                      setActiveTaskId(t.task_id);
                      setModalKind("reassign");
                    }}
                  >
                    改派
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
