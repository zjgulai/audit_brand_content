import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, request } from "../api/client";
import { useIdentity } from "../components/IdentitySwitcher";
import Button from "../ui/Button";
import Icon from "../ui/icon";

/**
 * 申诉中心（P-06 · Wave D 落 UJ-3 与 AP-1…AP-15 状态机，覆盖 `/appeals` 与 `/appeals/:appealId`）。
 *
 * 状态机：
 *   - `open`：已受理（2 个工作日 SLA）；
 *   - `paused_version_invalidated`：原案件因规则/正文变化触发重审，申诉自动暂停（不可直接受理/关闭）；
 *     仅原申诉人（actor === appellant）可在重审完成后点击「确认迁移至新版本（migrate）」（AP-3 / AP-4）；
 *   - `stale`：暂停满 30 天未确认自动转 stale（停止提醒、不关闭、长期保留，仍允许 migrate 或新申诉，AP-9…AP-14）；
 *   - `withdrawn`：原申诉人填写书面理由撤销（缺理由返 400）；
 *   - `resolved`：终态。
 */

export interface AppealItem {
  appeal_id: string;
  case_id: string;
  appellant: string;
  reason: string;
  state:
    | "open"
    | "paused_version_invalidated"
    | "migrated"
    | "stale"
    | "withdrawn"
    | "resolved"
    | string;
  opened_at?: string;
  paused_at?: string | null;
  pause_reason?: string | null;
  migrated_at?: string | null;
  stale_at?: string | null;
  withdrawn_at?: string | null;
  withdraw_reason?: string | null;
}

export default function AppealsPage() {
  const { appealId } = useParams<{ appealId: string }>();
  const { devEnabled, current, sessionEpoch } = useIdentity();

  const [rows, setRows] = useState<AppealItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ ok: boolean; text: string } | null>(
    null,
  );
  const [busy, setBusy] = useState<boolean>(false);

  const [newCaseId, setNewCaseId] = useState<string>("");
  const [newReason, setNewReason] = useState<string>("");
  const [withdrawReason, setWithdrawReason] = useState<string>("");

  const loadAppeals = useCallback(async () => {
    try {
      const data = await request<AppealItem[]>("/appeals");
      setRows(Array.isArray(data) ? data : []);
      setError(null);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message ?? String(e));
    }
  }, []);

  useEffect(() => {
    if (devEnabled && current === null) {
      setRows(null);
      return;
    }
    void loadAppeals();
  }, [current, devEnabled, loadAppeals, sessionEpoch]);

  const handleCreateAppeal = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!newCaseId.trim() || !newReason.trim() || busy) return;
    setBusy(true);
    setFlash(null);
    try {
      const created = await request<AppealItem>("/appeals", {
        method: "POST",
        body: {
          case_id: newCaseId.trim(),
          reason: newReason.trim(),
        },
        idempotencyKey: crypto.randomUUID(),
      });
      setRows((prev) => [created, ...(prev ?? [])]);
      setNewCaseId("");
      setNewReason("");
      setFlash({
        ok: true,
        text: `申诉 ${created.appeal_id} 已受理（状态：${created.state}，SLA：2 个工作日）。`,
      });
    } catch (cause: unknown) {
      const msg =
        cause instanceof ApiError
          ? `HTTP ${cause.status}: ${cause.message}`
          : String(cause);
      setFlash({ ok: false, text: `发起申诉未完成：${msg}` });
    } finally {
      setBusy(false);
    }
  };

  const handleMigrate = async (item: AppealItem) => {
    if (busy) return;
    setBusy(true);
    setFlash(null);
    try {
      const updated = await request<AppealItem>(
        `/appeals/${encodeURIComponent(item.appeal_id)}/migrate`,
        {
          method: "POST",
          body: {},
          idempotencyKey: crypto.randomUUID(),
        },
      );
      setRows((prev) =>
        (prev ?? []).map((x) =>
          x.appeal_id === item.appeal_id ? updated : x,
        ),
      );
      setFlash({
        ok: true,
        text: `申诉 ${item.appeal_id} 已确认迁移至重审新版本（migrated）。`,
      });
    } catch (cause: unknown) {
      const msg =
        cause instanceof ApiError
          ? `HTTP ${cause.status}: ${cause.message}`
          : String(cause);
      setFlash({ ok: false, text: `迁移被拒绝：${msg}` });
    } finally {
      setBusy(false);
    }
  };

  const handleWithdraw = async (item: AppealItem) => {
    if (!withdrawReason.trim() || busy) return;
    setBusy(true);
    setFlash(null);
    try {
      const updated = await request<AppealItem>(
        `/appeals/${encodeURIComponent(item.appeal_id)}/withdraw`,
        {
          method: "POST",
          body: { reason: withdrawReason.trim() },
          idempotencyKey: crypto.randomUUID(),
        },
      );
      setRows((prev) =>
        (prev ?? []).map((x) =>
          x.appeal_id === item.appeal_id ? updated : x,
        ),
      );
      setWithdrawReason("");
      setFlash({
        ok: true,
        text: `申诉 ${item.appeal_id} 已附书面理由撤销（withdrawn）。`,
      });
    } catch (cause: unknown) {
      const msg =
        cause instanceof ApiError
          ? `HTTP ${cause.status}: ${cause.message}`
          : String(cause);
      setFlash({ ok: false, text: `撤销失败：${msg}` });
    } finally {
      setBusy(false);
    }
  };

  const renderStateBadge = (state: string) => {
    if (state === "open") {
      return (
        <span className="badge badge--pending" data-status-badge="">
          open（受理中 · 2工作日 SLA）
        </span>
      );
    }
    if (state === "paused_version_invalidated") {
      return (
        <span className="badge badge--warn" data-status-badge="">
          paused（版本失效暂停）
        </span>
      );
    }
    if (state === "stale") {
      return (
        <span className="badge badge--sample" data-status-badge="">
          stale（超30天未确认 · 长期保留）
        </span>
      );
    }
    if (state === "migrated" || state === "resolved") {
      return (
        <span className="badge badge--pass" data-status-badge="">
          {state}
        </span>
      );
    }
    return (
      <span className="badge badge--untested" data-status-badge="">
        {state}
      </span>
    );
  };

  const selected = appealId
    ? (rows ?? []).find((r) => r.appeal_id === appealId)
    : null;

  return (
    <section className="cases-page" aria-labelledby="appeals-page-title">
      <div className="cases-page__head">
        <div>
          <h1 id="appeals-page-title">
            {appealId ? `申诉详情 · ${appealId}` : "申诉中心（P-06）"}
          </h1>
          <p className="hint">
            案件号即回执号；DP3 受理 SLA 为 2 个工作日；争议指向规则本身时升级法务（DP4）。
            原案件失效重审时申诉自动暂停（<code>version_invalidated</code>），不自动关闭或自动迁移（AP-1 / AP-2）。
          </p>
        </div>
        {appealId && (
          <Link to="/appeals" className="btn">
            <Icon name="arrow-left" size={12} /> 返回申诉列表
          </Link>
        )}
      </div>

      {error && (
        <div className="state state--error" role="alert">
          读取申诉数据失败：{error}
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

      {appealId && selected ? (
        <div className="state">
          <div className="evidence__head">
            <span className="font-data">
              <strong>{selected.appeal_id}</strong>
            </span>
            {renderStateBadge(selected.state)}
          </div>

          {selected.state === "paused_version_invalidated" && (
            <div className="state state--warn" role="note">
              <strong>版本失效暂停保护（AP-1 / AP-5）</strong>：原案件因规则、依据或内容更新已触发全量重审，
              当前申诉处于暂停态，不得直接受理、驳回或关闭。重审完成后，仅<strong>原申诉人</strong>可确认迁移至新版本。
            </div>
          )}

          {selected.state === "stale" && (
            <div className="state" role="note">
              <strong>逾期未确认长期保留（AP-9…AP-14）</strong>：暂停已满 30 天未确认，已停止每日提醒，
              但记录与材料长期保留且不自动关闭；原申诉人仍可确认迁移或针对新版本发起新申诉。
            </div>
          )}

          <dl className="facts">
            <dt>关联案件 / 回执</dt>
            <dd className="font-data">
              <Link to={`/cases/${encodeURIComponent(selected.case_id)}`}>
                {selected.case_id}
              </Link>
            </dd>
            <dt>原申诉人</dt>
            <dd className="font-data">{selected.appellant}</dd>
            <dt>申诉理由</dt>
            <dd>{selected.reason}</dd>
            <dt>发起时间</dt>
            <dd className="font-data">{selected.opened_at ?? "未记录"}</dd>
          </dl>

          <div className="submit-field">
            <label htmlFor="appeal-withdraw-reason">
              撤销书面理由（撤销申诉必填，AP / C2）
            </label>
            <input
              id="appeal-withdraw-reason"
              type="text"
              value={withdrawReason}
              onChange={(e) => setWithdrawReason(e.target.value)}
              placeholder="填写撤销该申诉的具体原因…"
            />
          </div>

          <div className="actions__row">
            <Button
              variant="secondary"
              disabled={
                busy ||
                (selected.state !== "paused_version_invalidated" &&
                  selected.state !== "stale") ||
                current?.id !== selected.appellant
              }
              onClick={() => void handleMigrate(selected)}
            >
              确认迁移至重审新版本（Migrate）
            </Button>
            <Button
              variant="secondary"
              disabled={
                busy ||
                !withdrawReason.trim() ||
                current?.id !== selected.appellant
              }
              onClick={() => void handleWithdraw(selected)}
            >
              附理由撤销申诉（Withdraw）
            </Button>
          </div>
        </div>
      ) : (
        <>
          <div className="panel">
            <h2 className="panel__title">发起新申诉</h2>
            <form
              className="submit-form"
              onSubmit={(e) => void handleCreateAppeal(e)}
            >
              <div className="submit-grid">
                <div>
                  <label htmlFor="appeal-case-id">
                    案件编号 / 回执号（必填）
                  </label>
                  <input
                    id="appeal-case-id"
                    type="text"
                    className="font-data"
                    value={newCaseId}
                    onChange={(e) => setNewCaseId(e.target.value)}
                    placeholder="例如 case-smoke"
                  />
                </div>
                <div>
                  <label htmlFor="appeal-reason">申诉异议理由（必填）</label>
                  <input
                    id="appeal-reason"
                    type="text"
                    value={newReason}
                    onChange={(e) => setNewReason(e.target.value)}
                    placeholder="说明误判原因或补充合规依据…"
                  />
                </div>
              </div>
              <div className="actions__row">
                <Button
                  type="submit"
                  variant="secondary"
                  disabled={busy || !newCaseId.trim() || !newReason.trim()}
                >
                  提交申诉
                </Button>
              </div>
            </form>
          </div>

          <h2>申诉记录列表（共 {(rows ?? []).length} 条）</h2>
          {rows === null ? (
            <p className="hint">加载中…</p>
          ) : rows.length === 0 ? (
            <div className="empty">
              <p className="empty__title">当前租户暂无申诉记录</p>
              <p>申诉由内容提交方发起；提交后在此按 SLA 受理与迁移。</p>
            </div>
          ) : (
            <div className="cases-table-wrap">
              <table className="cases-table">
                <thead>
                  <tr>
                    <th scope="col">申诉编号</th>
                    <th scope="col">关联案件</th>
                    <th scope="col">申诉人</th>
                    <th scope="col">状态</th>
                    <th scope="col">申诉理由</th>
                    <th scope="col">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.appeal_id}>
                      <td className="font-data">
                        <Link
                          to={`/appeals/${encodeURIComponent(r.appeal_id)}`}
                        >
                          {r.appeal_id}
                        </Link>
                      </td>
                      <td className="font-data">
                        <Link to={`/cases/${encodeURIComponent(r.case_id)}`}>
                          {r.case_id}
                        </Link>
                      </td>
                      <td className="font-data">{r.appellant}</td>
                      <td>{renderStateBadge(r.state)}</td>
                      <td className="cases-table__excerpt">{r.reason}</td>
                      <td>
                        <Link
                          to={`/appeals/${encodeURIComponent(r.appeal_id)}`}
                          className="btn"
                        >
                          查看与处置
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
