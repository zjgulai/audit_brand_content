import { useRef, useState } from "react";

import { ApiError, type CaseDetail } from "../api/client";
import { useIdentity } from "./IdentitySwitcher";

interface Props {
  detail: CaseDetail;
  refresh: () => Promise<CaseDetail | null>;
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

export default function DevReviewActions({ detail, refresh }: Props) {
  const { current } = useIdentity();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<{
    kind: "ok" | "error" | "warn";
    text: string;
  } | null>(null);
  const [formalId, setFormalId] = useState<string | null>(null);
  const [acceptedWithoutReadback, setAcceptedWithoutReadback] = useState(false);
  const [retryIntent, setRetryIntent] = useState<RetryIntent | null>(null);
  const pendingRef = useRef(false);

  const review = detail.review;
  const leaseActive =
    typeof review?.lease_expires === "number" && review.lease_expires > Date.now() / 1000;
  const canEditClaim =
    current !== null &&
    review?.status === "claimed" &&
    review.assignee === current.id &&
    leaseActive;
  const canClaim =
    current !== null && review?.status !== "claimed" && review?.status !== "closed";
  const hasReason = note.trim().length > 0;

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
      if (cause instanceof ApiError && ![408, 429].includes(cause.status) && cause.status < 500) {
        const why =
          cause.status === 409
            ? "版本或领取状态已变化；请保留文字并刷新，不会自动覆盖重交"
            : cause.status === 403
              ? "当前身份无权执行该动作"
              : cause.message;
        setRetryIntent(null);
        setFlash({ kind: "error", text: `${intent.name} 失败（${cause.status}）：${why}` });
      } else {
        // 网络错误、408/429/5xx 都可能已在服务端生效：保留原始 closure 与 key。
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
          className={"state " + (flash.kind === "error" ? "state--error" : "state--warn")}
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
      <label htmlFor="review-note">复核理由 / 备注</label>
      <textarea
        id="review-note"
        value={note}
        onChange={(event) => {
          setNote(event.target.value);
          setRetryIntent(null); // 载荷变化是新意图，不复用旧 key。
        }}
        placeholder="只记录人工复核意见；不改变机器标签，也不代表放行。"
      />
      <div className="actions__row" style={{ marginTop: "0.6rem" }}>
        <button
          type="button"
          className="btn btn--primary"
          disabled={busy !== null || !canClaim}
          onClick={() =>
            startIntent("认领", async (key) => {
              const { reviewWriteApi } = await import("../api/write-client");
              return reviewWriteApi.claim(detail.case_id, key);
            })
          }
        >
          认领
        </button>
        <button
          type="button"
          className="btn"
          disabled={busy !== null || !canEditClaim || !hasReason || review === null}
          onClick={() =>
            startIntent("存草稿", async (key) => {
              const { reviewWriteApi } = await import("../api/write-client");
              return reviewWriteApi.saveDraft(
                detail.case_id,
                review!.version,
                { form: {}, notes: note.trim(), evidence_selections: [] },
                key,
              );
            })
          }
        >
          存草稿
        </button>
        <button
          type="button"
          className="btn"
          disabled={busy !== null || !canEditClaim || !hasReason || review === null}
          onClick={() =>
            startIntent("提交复核意见", async (key) => {
              const { reviewWriteApi } = await import("../api/write-client");
              return reviewWriteApi.submitConclusion(
                detail.case_id,
                review!.version,
                { review_notes: note.trim() },
                key,
              );
            })
          }
        >
          提交复核意见
        </button>
        {retryIntent && busy === null && (
          <button type="button" className="btn" onClick={() => void runIntent(retryIntent)}>
            重试同一请求
          </button>
        )}
      </div>
      {review?.primary_draft_id && note.length === 0 && (
        <p className="actions__note">
          服务端已有主草稿 <code>{review.primary_draft_id}</code>，但当前 API 只返回 ID，
          不能恢复草稿正文；请勿把空输入框理解为无草稿。
        </p>
      )}
      {formalId && (
        <p className="actions__note">
          本页提交的正式记录：<code>{formalId}</code>。当前 GET 只回读 closed/version，
          刷新后不能恢复正式记录正文。
        </p>
      )}
    </>
  );
}
