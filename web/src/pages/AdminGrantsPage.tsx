import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError, request } from "../api/client";
import { useIdentity } from "../components/IdentitySwitcher";
import Button from "../ui/Button";

/**
 * 授权名单治理（P-11 · Wave E 落 §1.5 与 GR-1…GR-18 三权分立台账）。
 *
 * 1. 覆盖签发授权（`signer-grants`：`release.sign` / `release.revoke`）与
 *    下线授权（`takedown-grants`：`takedown.execute` / `takedown.waive`）；
 * 2. 三权分立（SoD）：提案人（Proposer） !== 执行人（Executor） !== 第二审批人（Approver）；
 * 3. 明确标注历史签名保留原则（GR-10…GR-12）：撤销授权后既有签名仍有效，且原签发人仍可撤回自己的历史签名。
 */

export interface GrantRecord {
  grant_id?: string;
  id?: string;
  tenant?: string;
  product_line?: string;
  platform?: string;
  user_id?: string;
  capability?: string;
  status?: string;
  // T-314d：三态走 state（reducer 的真相源）；status 仅为旧数据兜底。
  state?: "proposed" | "executed" | "approved" | "revoked" | string;
  proposed_at?: string;
  executed_at?: string;
  approved_at?: string;
  revoked_by?: string;
  revoked_at?: string;
  revoke_reason?: string;
  proposed_by?: string;
  executed_by?: string;
  approved_by?: string;
  reason?: string;
}

export default function AdminGrantsPage() {
  const { devEnabled, current, sessionEpoch } = useIdentity();
  const [tab, setTab] = useState<"signer" | "takedown">("signer");
  const [signerGrants, setSignerGrants] = useState<GrantRecord[] | null>(null);
  const [takedownGrants, setTakedownGrants] = useState<GrantRecord[] | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ ok: boolean; text: string } | null>(
    null,
  );
  const [busy, setBusy] = useState<boolean>(false);

  const [targetUser, setTargetUser] = useState<string>("");
  const [capability, setCapability] = useState<string>("release.sign");
  const [productLine, setProductLine] = useState<string>("pump");
  const [platform, setPlatform] = useState<string>("amazon");
  const [reason, setReason] = useState<string>("");

  const loadGrants = useCallback(async () => {
    try {
      const [sg, tg] = await Promise.all([
        request<GrantRecord[]>("/admin/signer-grants"),
        request<GrantRecord[]>("/admin/takedown-grants"),
      ]);
      setSignerGrants(Array.isArray(sg) ? sg : []);
      setTakedownGrants(Array.isArray(tg) ? tg : []);
      setError(null);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 403) {
        setError(
          "仅内部治理角色可读取授权台账。",
        );
      } else {
        const err = e as { message?: string };
        setError(err.message ?? String(e));
      }
    }
  }, []);

  useEffect(() => {
    if (devEnabled && current === null) return;
    void loadGrants();
  }, [current, devEnabled, loadGrants, sessionEpoch]);

  const handlePropose = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!targetUser.trim() || !reason.trim() || busy) return;
    setBusy(true);
    setFlash(null);
    const path =
      tab === "signer" ? "/admin/signer-grants" : "/admin/takedown-grants";
    try {
      await request(path, {
        method: "POST",
        body: {
          user_id: targetUser.trim(),
          capability,
          product_line: productLine,
          ...(tab === "takedown" ? { platform } : {}),
          reason: reason.trim(),
        },
        idempotencyKey: crypto.randomUUID(),
      });
      setFlash({
        ok: true,
        text: "授权提案已提交，等待独立执行人与第二审批人完成三权分立核准。",
      });
      await loadGrants();
    } catch (cause: unknown) {
      if (cause instanceof ApiError) {
        setFlash({
          ok: false,
          text: `提交响应（HTTP ${cause.status}）：${cause.message}`,
        });
      } else {
        setFlash({ ok: false, text: String(cause) });
      }
    } finally {
      setBusy(false);
    }
  };

  // T-314d：执行 / 审批两段。★ 显隐只是减少误点；真正的三主体判定在
  // 后端 validate_grant_actors 与 reducer 的逐步校验（curl 直打照样 403，
  // 反向对照在 verify_grant_registry G11/G12）。
  const handleTransition = async (grant: GrantRecord, action: "execute" | "approve") => {
    if (busy || !grant.grant_id && !grant.id) return;
    setBusy(true);
    setFlash(null);
    const gid = String(grant.grant_id ?? grant.id);
    try {
      await request(`/admin/grants/${encodeURIComponent(gid)}/${action}`, {
        method: "POST",
        body: { note: `${action === "execute" ? "执行" : "审批"}自 P-11` },
        idempotencyKey: crypto.randomUUID(),
      });
      setFlash({
        ok: true,
        text:
          action === "execute"
            ? "已执行，等待第二审批人核准。"
            : "已核准，授权进入 approved。",
      });
      await loadGrants();
    } catch (cause: unknown) {
      if (cause instanceof ApiError) {
        setFlash({
          ok: false,
          text: `响应（HTTP ${cause.status}）：${cause.message}`,
        });
      } else {
        setFlash({ ok: false, text: String(cause) });
      }
    } finally {
      setBusy(false);
    }
  };

  const activeRows = tab === "signer" ? signerGrants : takedownGrants;

  return (
    <section className="cases-page" aria-labelledby="admin-grants-title">
      <div className="cases-page__head">
        <div>
          <h1 id="admin-grants-title">授权治理</h1>
          <p className="hint">
            管理合规签发与违规下架的操作权限。权限变更需经提案、执行与审批三方确认。
          </p>
        </div>
        <div className="queue__filters" role="tablist" aria-label="授权类别切换">
          <button
            type="button"
            role="tab"
            className="queue__filter"
            aria-selected={tab === "signer"}
            aria-pressed={tab === "signer"}
            onClick={() => {
              setTab("signer");
              setCapability("release.sign");
            }}
          >
            签发权限
          </button>
          <button
            type="button"
            role="tab"
            className="queue__filter"
            aria-selected={tab === "takedown"}
            aria-pressed={tab === "takedown"}
            onClick={() => {
              setTab("takedown");
              setCapability("takedown.execute");
            }}
          >
            下架权限
          </button>
        </div>
      </div>

      {error && (
        <div className="state state--forbidden" role="alert">
          <h2>权限受限</h2>
          <p>{error}</p>
        </div>
      )}

      {flash && (
        <div
          className={"state " + (flash.ok ? "" : "state--warn")}
          role="status"
        >
          {flash.text}
        </div>
      )}

      <div className="actions">
        <h2>新增权限申请</h2>
        <form className="submit-form" onSubmit={(e) => void handlePropose(e)}>
          <div className="submit-grid">
            <div>
              <label htmlFor="grant-user">被授权人账号</label>
              <input
                id="grant-user"
                type="text"
                className="font-data"
                value={targetUser}
                onChange={(e) => setTargetUser(e.target.value)}
                placeholder="例如 u_legal_01"
              />
            </div>
            <div>
              <label htmlFor="grant-cap">权限类型</label>
              <select
                id="grant-cap"
                value={capability}
                onChange={(e) => setCapability(e.target.value)}
              >
                {tab === "signer" ? (
                  <>
                    <option value="release.sign">release.sign（签发）</option>
                    <option value="release.revoke">
                      release.revoke（撤回，需二次审批）
                    </option>
                  </>
                ) : (
                  <>
                    <option value="takedown.execute">
                      takedown.execute（执行下线）
                    </option>
                    <option value="takedown.waive">
                      takedown.waive（审批下线豁免）
                    </option>
                  </>
                )}
              </select>
            </div>
            <div>
              <label htmlFor="grant-line">适用产品线</label>
              <select
                id="grant-line"
                value={productLine}
                onChange={(e) => setProductLine(e.target.value)}
              >
                <option value="pump">pump</option>
                <option value="wearable">wearable</option>
                <option value="feeding">feeding</option>
                <option value="skincare">skincare</option>
              </select>
            </div>
            {tab === "takedown" && (
              <div>
                <label htmlFor="grant-platform">适用投放渠道</label>
                <select
                  id="grant-platform"
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value)}
                >
                  <option value="amazon">amazon</option>
                  <option value="tiktok">tiktok</option>
                  <option value="shopify">shopify</option>
                </select>
              </div>
            )}
          </div>
          <div className="submit-field">
            <label htmlFor="grant-reason">授权提案书面理由（必填）</label>
            <input
              id="grant-reason"
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="说明新增或调整权限的业务原因…"
            />
          </div>
          <div className="actions__row">
            <Button
              type="submit"
              variant="secondary"
              disabled={busy || !targetUser.trim() || !reason.trim()}
            >
              提交授权提案
            </Button>
          </div>
        </form>
      </div>

      <h2>当前授权台账列表</h2>
      {activeRows === null ? (
        <p className="hint">{error ? "无可读数据。" : "加载中…"}</p>
      ) : activeRows.length === 0 ? (
        <div className="state">
          <p className="hint">暂无授权记录。</p>
        </div>
      ) : (
        <div className="cases-table-wrap">
          <table className="cases-table">
            <thead>
              <tr>
                <th scope="col">授权 ID</th>
                <th scope="col">被授权人</th>
                <th scope="col">权限与适用范围</th>
                <th scope="col">提案 / 执行 / 二次审批</th>
                <th scope="col">状态</th>
              </tr>
            </thead>
            <tbody>
              {activeRows.map((g, i) => (
                <tr key={g.grant_id ?? g.id ?? i}>
                  <td className="font-data">{g.grant_id ?? g.id ?? `#${i + 1}`}</td>
                  <td className="font-data">{g.user_id ?? "未记录"}</td>
                  <td className="font-data">
                    {g.capability ?? "未指定"}，{g.product_line ?? "all"}
                    {g.platform ? ` ${g.platform}` : ""}
                  </td>
                  <td className="font-data">
                    P:{g.proposed_by ?? "-"} / E:{g.executed_by ?? "-"} / A:
                    {g.approved_by ?? "-"}
                  </td>
                  <td>
                    <span className="badge badge--pending" data-status-badge="">
                      {g.state ?? g.status ?? "active"}
                    </span>
                    {(g.state ?? g.status) === "proposed" && (
                      <button
                        type="button"
                        className="btn"
                        disabled={busy}
                        onClick={() => handleTransition(g, "execute")}
                      >
                        执行
                      </button>
                    )}
                    {(g.state ?? g.status) === "executed" && (
                      <button
                        type="button"
                        className="btn"
                        disabled={busy}
                        onClick={() => handleTransition(g, "approve")}
                      >
                        审批
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
