import { useRef, useState } from "react";
import { ApiError, type CaseDetail, type DraftSnapshot } from "../api/client";
import Button from "../ui/Button";
import Icon from "../ui/icon";
import { useIdentity } from "./IdentitySwitcher";

/**
 * 复核动作与草稿交接面板（Wave B · 落 G-07 决策，修 D-07）。
 *
 * 功能：
 *   1. 认领（claim）/ 释放认领（unclaim）/ 改派（reassign）/ 租约续期（heartbeat）；
 *   2. 手动存草稿快照（save_draft）：认领且租约有效时，点击「存草稿」生成快照并回显服务端 snapshot_seq
 *      （为保证乐观锁 version 单调可控与 check_review_actions.mjs 联调门契约一致，不启用后台定时自动保存）；
 *   3. 前人草稿交接抽屉（Draft Handoff）：
 *      - 只读查看全部历史草稿（author / snapshot_at / snapshot_seq / notes）；
 *      - 最新 primary 草稿带视觉标记「Recommended: Latest」，不自动预选；
 *      - 支持显式 Adopt primary 草稿（记录 derived_from）与对非 primary 草稿引用片段（reference_fragment）；
 *   4. 保留 `#review-note` 原生 textarea 与「认领」「存草稿」「提交复核意见」按钮文案。
 */

interface Props {
  detail: CaseDetail;
  refresh: () => Promise<CaseDetail | null>;
  mode?: "prod" | "dev";
}

interface RetryIntent {
  name: string;
  key: string;
  execute: () => Promise<unknown>;
}

function mutationVersion(value: unknown): number | null {
  if (!value || typeof value !== "object" || !("version" in value)) return null;
  return typeof value.version === "number" ? value.version : null;
}

function readbackProblem(response: unknown, refreshed: CaseDetail): string | null {
  const version = mutationVersion(response);
  if (version === null) return "写响应缺少 version";
  if (refreshed.review?.version !== version) {
    return `台账版本未同步（响应 ${version} / 回读 ${refreshed.review?.version ?? "未读取"}）`;
  }
  if (response && typeof response === "object" && "draft" in response) {
    const draft = response.draft;
    const draftId =
      draft && typeof draft === "object" && "draft_id" in draft
        ? String(draft.draft_id)
        : null;
    if (!draftId || refreshed.review?.primary_draft_id !== draftId) {
      return "主草稿 ID 未在 GET 台账摘要中回读";
    }
  }
  if (
    response &&
    typeof response === "object" &&
    "formal" in response &&
    response.formal !== null
  ) {
    if (refreshed.review?.status !== "closed") return "提交后台账未回读为 closed";
  }
  return null;
}

function actionErrorMessage(cause: ApiError): string {
  if (cause.status === 409) {
    if (cause.code === "invalid_finding_transition") {
      return "该 finding 已不是 candidate（可能已被他人裁决）；请刷新";
    }
    return "版本或领取状态已变化；请保留文字并刷新，不会自动覆盖重交";
  }
  if (cause.status === 404 && cause.code === "finding_not_found") {
    return "finding 不存在或已被移除；请刷新";
  }
  if (cause.status === 501 || cause.code === "capability_not_enabled") {
    return "该能力尚未开启（501）；不要重试";
  }
  if (cause.status === 403) return "当前身份无权执行该动作";
  return cause.message;
}

export default function ReviewActions({ detail, refresh }: Props) {
  const { current } = useIdentity();
  const review = detail.review;
  const primaryDraft = review?.primary_draft ?? null;
  const drafts: DraftSnapshot[] = review?.drafts ?? [];

  const [note, setNote] = useState<string>("");
  const [verdictChoice, setVerdictChoice] = useState<
    "uphold" | "revise" | "override_pass"
  >("uphold");
  const [reassignTarget, setReassignTarget] = useState<string>("");
  const [showHandoff, setShowHandoff] = useState<boolean>(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<{
    kind: "ok" | "error" | "warn";
    text: string;
  } | null>(null);
  const [formalId, setFormalId] = useState<string | null>(null);
  const [acceptedWithoutReadback, setAcceptedWithoutReadback] = useState(false);
  const [retryIntent, setRetryIntent] = useState<RetryIntent | null>(null);
  const [autoSaveInfo, setAutoSaveInfo] = useState<string | null>(null);
  const pendingRef = useRef(false);

  const leaseActive =
    typeof review?.lease_expires === "number" &&
    review.lease_expires > Date.now() / 1000;
  const canEditClaim =
    current !== null &&
    review?.status === "claimed" &&
    review.assignee === current.id &&
    leaseActive;
  const canClaim =
    current !== null &&
    review?.status !== "claimed" &&
    review?.status !== "closed";
  const candidates = (detail.ir.findings ?? []).filter(
    (f) => f.status === "candidate",
  );

  const getWriteApi = async () => {
    const mod = await import("../api/write-client");
    return mod.reviewWriteApi;
  };

  const runIntent = async (intent: RetryIntent) => {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setBusy(intent.name);
    setFlash(null);
    setAcceptedWithoutReadback(false);
    try {
      const response = await intent.execute();
      setRetryIntent(null);
      if (
        response &&
        typeof response === "object" &&
        "formal" in response &&
        response.formal &&
        typeof response.formal === "object" &&
        "formal_id" in response.formal
      ) {
        setFormalId(String(response.formal.formal_id));
      }
      if (
        response &&
        typeof response === "object" &&
        "draft" in response &&
        response.draft &&
        typeof response.draft === "object" &&
        "snapshot_seq" in response.draft
      ) {
        setAutoSaveInfo(
          `草稿快照 #${String(response.draft.snapshot_seq)} 已同步`,
        );
      }
      const refreshed = await refresh();
      if (!refreshed) {
        setAcceptedWithoutReadback(true);
        setFlash({
          kind: "warn",
          text: `${intent.name} 请求已接受，但台账回读未完成；请勿创建新请求。`,
        });
        return;
      }
      const problem = readbackProblem(response, refreshed);
      if (problem) {
        setAcceptedWithoutReadback(true);
        setFlash({
          kind: "warn",
          text: `${intent.name} 请求已接受，但${problem}；请先刷新核对。`,
        });
        return;
      }
      setFlash({ kind: "ok", text: `${intent.name} 已完成并回读台账` });
    } catch (cause: unknown) {
      if (
        cause instanceof ApiError &&
        ![408, 429].includes(cause.status) &&
        cause.status < 500
      ) {
        setRetryIntent(null);
        setFlash({
          kind: "error",
          text: `${intent.name} 失败（${cause.status}）：${actionErrorMessage(cause)}`,
        });
      } else {
        setRetryIntent(intent);
        setFlash({
          kind: "warn",
          text: `${intent.name} 结果未知；保留同一幂等键，只有你点击重试才会重发。`,
        });
      }
    } finally {
      pendingRef.current = false;
      setBusy(null);
    }
  };

  const startIntent = (
    name: string,
    execute: (key: string) => Promise<unknown>,
  ) => {
    const key = crypto.randomUUID();
    void runIntent({ name, key, execute: () => execute(key) });
  };

  return (
    <>
      {flash && (
        <div
          className={
            "state " + (flash.kind === "error" ? "state--error" : "state--warn")
          }
          role={flash.kind === "error" ? "alert" : "status"}
        >
          {flash.text}
        </div>
      )}
      {acceptedWithoutReadback && (
        <div className="state state--warn" role="alert">
          不确定状态下不要开始新动作。刷新确认台账版本后再继续。
        </div>
      )}

      {/* 前人草稿交接（Draft Handoff）横幅与对比抽屉 */}
      {drafts.length > 0 && (
        <div className="handoff-bar" data-draft-handoff="">
          <div className="handoff-bar__summary">
            <Icon name="history" size={13} />{" "}
            <span>
              历史草稿快照：共 <strong>{drafts.length}</strong> 份
              {primaryDraft && (
                <>
                  {" "}
                  · 当前主草稿 <code>{primaryDraft.draft_id}</code>（#
                  {primaryDraft.snapshot_seq} · 作者{" "}
                  <code>{primaryDraft.author ?? "未知"}</code>）
                </>
              )}
            </span>
          </div>
          <Button
            variant="secondary"
            onClick={() => setShowHandoff(!showHandoff)}
          >
            {showHandoff ? "收起草稿交接" : "查看/交接历史草稿"}
          </Button>
        </div>
      )}

      {showHandoff && drafts.length > 0 && (
        <div className="handoff-drawer" role="region" aria-label="历史草稿交接对比">
          <p className="hint">
            原稿不可变（Immutable）。系统仅视觉标记最新主草稿（Recommended: Latest），不自动预选或自动合并：
            主草稿须<strong>显式 Adopt</strong>以生成新派生草稿（记录 <code>derived_from</code>）；其余历史快照可<strong>引用片段（Reference）</strong>。
          </p>
          <ul className="handoff-list">
            {drafts.map((d) => {
              const isPrimary = d.draft_id === review?.primary_draft_id;
              return (
                <li key={d.draft_id} className="handoff-card">
                  <div className="handoff-card__head">
                    <span className="font-data">
                      <strong>#{d.snapshot_seq}</strong> · {d.draft_id}
                    </span>
                    <span className="hint">
                      作者 <code>{d.author ?? "システム"}</code> · {d.snapshot_at}
                    </span>
                    {isPrimary && (
                      <span className="badge badge--pending" data-status-badge="">
                        Recommended: Latest (Primary)
                      </span>
                    )}
                    {d.derived_from && (
                      <span className="hint font-data">
                        派生自 {d.derived_from}
                      </span>
                    )}
                  </div>
                  <div className="evidence__quote">
                    {d.notes || "（空草稿备注）"}
                  </div>
                  <div className="actions__row">
                    {isPrimary ? (
                      <Button
                        variant="secondary"
                        disabled={busy !== null || !canEditClaim || review === null}
                        onClick={() =>
                          startIntent(`采纳主草稿 ${d.draft_id}`, async (key) => {
                            const api = await getWriteApi();
                            const res = await api.adoptDraft(
                              detail.case_id,
                              review!.version,
                              d.draft_id,
                              key,
                            );
                            if (d.notes) setNote(d.notes);
                            return res;
                          })
                        }
                      >
                        显式采纳为主草稿（Adopt）
                      </Button>
                    ) : (
                      <Button
                        variant="secondary"
                        disabled={
                          busy !== null ||
                          !canEditClaim ||
                          review === null ||
                          !d.notes
                        }
                        onClick={() =>
                          startIntent(`引用草稿片段 ${d.draft_id}`, async (key) => {
                            const api = await getWriteApi();
                            const res = await api.referenceFragment(
                              detail.case_id,
                              review!.version,
                              d.draft_id,
                              "notes",
                              d.notes,
                              key,
                            );
                            setNote((prev) =>
                              prev
                                ? `${prev}\n[引用 ${d.draft_id}]: ${d.notes}`
                                : `[引用 ${d.draft_id}]: ${d.notes}`,
                            );
                            return res;
                          })
                        }
                      >
                        引用备注片段（Reference）
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div className="verdict-picker" role="group" aria-label="人工复核倾向">
        <span className="hint">复核处置倾向：</span>
        <label className="verdict-radio">
          <input
            type="radio"
            name={`verdict-${detail.case_id}`}
            checked={verdictChoice === "uphold"}
            onChange={() => setVerdictChoice("uphold")}
          />
          <span>维持机器判定建议</span>
        </label>
        <label className="verdict-radio">
          <input
            type="radio"
            name={`verdict-${detail.case_id}`}
            checked={verdictChoice === "revise"}
            onChange={() => setVerdictChoice("revise")}
          />
          <span>要求内容方改写重提</span>
        </label>
        <label className="verdict-radio">
          <input
            type="radio"
            name={`verdict-${detail.case_id}`}
            checked={verdictChoice === "override_pass"}
            onChange={() => setVerdictChoice("override_pass")}
          />
          <span>人工复核通过（仍待签发）</span>
        </label>
      </div>

      <label htmlFor="review-note">
        复核理由 / 备注 / 裁决理由
        {autoSaveInfo && <span className="hint"> · {autoSaveInfo}</span>}
      </label>
      <textarea
        id="review-note"
        value={note}
        onChange={(event) => {
          setNote(event.target.value);
          setRetryIntent(null);
        }}
        placeholder="只记录人工复核意见；不改变机器标签，也不代表放行。"
      />

      <div className="actions__row">
        <Button
          variant="secondary"
          data-action="claim"
          disabled={busy !== null || !canClaim}
          onClick={() =>
            startIntent("认领", async (key) => {
              const api = await getWriteApi();
              return api.claim(detail.case_id, key);
            })
          }
        >
          认领
        </Button>
        {canEditClaim && review !== null && (
          <>
            <Button
              variant="secondary"
              data-action="unclaim"
              disabled={busy !== null}
              onClick={() =>
                startIntent("释放认领", async (key) => {
                  const api = await getWriteApi();
                  return api.unclaim(detail.case_id, review.version, key);
                })
              }
            >
              释放认领
            </Button>
            <Button
              variant="secondary"
              data-action="heartbeat"
              disabled={busy !== null}
              onClick={() =>
                startIntent("续期租约", async (key) => {
                  const api = await getWriteApi();
                  return api.heartbeat(detail.case_id, review.version, key);
                })
              }
            >
              续期租约
            </Button>
          </>
        )}
        <Button
          variant="secondary"
          data-action="draft"
          disabled={
            busy !== null || !canEditClaim || !note.trim() || review === null
          }
          onClick={() =>
            startIntent("存草稿", async (key) => {
              const api = await getWriteApi();
              return api.saveDraft(
                detail.case_id,
                review!.version,
                {
                  form: { verdict_choice: verdictChoice },
                  notes: note.trim(),
                  evidence_selections: [],
                },
                key,
              );
            })
          }
        >
          存草稿
        </Button>
        <Button
          variant="primary"
          data-risk-action="submit"
          data-action="submit"
          disabled={
            busy !== null || !canEditClaim || !note.trim() || review === null
          }
          onClick={() =>
            startIntent("提交复核意见", async (key) => {
              const api = await getWriteApi();
              return api.submitConclusion(
                detail.case_id,
                review!.version,
                {
                  review_notes: note.trim(),
                  verdict_choice: verdictChoice,
                },
                key,
              );
            })
          }
        >
          提交复核意见
        </Button>
        {retryIntent && busy === null && (
          <Button variant="secondary" onClick={() => void runIntent(retryIntent)}>
            重试同一请求
          </Button>
        )}
      </div>

      {/* 改派控件（认领存续期内可用） */}
      {canEditClaim && review !== null && (
        <div className="actions__row actions__reassign">
          <label htmlFor={`reassign-input-${detail.case_id}`} className="hint">
            改派给其他审核员/法务：
          </label>
          <input
            id={`reassign-input-${detail.case_id}`}
            type="text"
            value={reassignTarget}
            onChange={(e) => setReassignTarget(e.target.value)}
            placeholder="输入目标负责人账号 ID…"
            aria-label="输入改派目标负责人账号"
          />
          <Button
            variant="secondary"
            data-action="reassign"
            disabled={busy !== null || !reassignTarget.trim()}
            onClick={() =>
              startIntent(`改派至 ${reassignTarget.trim()}`, async (key) => {
                const api = await getWriteApi();
                return api.reassign(
                  detail.case_id,
                  review.version,
                  reassignTarget.trim(),
                  key,
                );
              })
            }
          >
            确认改派
          </Button>
        </div>
      )}

      {candidates.length > 0 && (
        <p className="hint">
          提示：上方「证据链」每条候选 finding 卡片内已支持直接点击「确认 / 驳回」就地裁决（共 {candidates.length} 条待裁）。
        </p>
      )}

      {formalId && (
        <p className="actions__note">
          本页提交的正式记录：<code>{formalId}</code>。人工意见不改变机器标签或放行状态。
        </p>
      )}
    </>
  );
}
