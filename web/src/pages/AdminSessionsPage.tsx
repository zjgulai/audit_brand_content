import { useCallback, useEffect, useState } from "react";
import { ApiError, request } from "../api/client";
import { useIdentity } from "../components/IdentitySwitcher";

/**
 * 会话与安全审计（P-12 · Wave E 落 SD-1…SD-18 与 C-103 / C-104 审计面板）。
 *
 * 1. 消费 `GET /api/v1/admin/sessions`（生产模式下后端按设计返 404，仅非生产或内部审计面开放）；
 * 2. 展示会话隔离原则（session.db 与 projection DB 独立、不进备份、恢复全失效）与
 *    C-103 只读入口拦截审计 / C-104 身份绑定审计规范。
 */
export default function AdminSessionsPage() {
  const { devEnabled, current, sessionEpoch } = useIdentity();
  const [sessions, setSessions] = useState<Array<Record<string, unknown>> | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    try {
      const data = await request<Array<Record<string, unknown>>>(
        "/admin/sessions",
      );
      setSessions(Array.isArray(data) ? data : []);
      setError(null);
    } catch (e: unknown) {
      if (e instanceof ApiError) {
        if (e.status === 403) {
          setError(
            "403 · 仅内部治理角色（IT 管理员 / 项目统筹）可访问会话与安全审计（internal_dep）。",
          );
        } else if (e.status === 404) {
          setError(
            "404 · 生产环境默认关闭在线枚举会话列表（SD-1 / review_api.py:714），会话审计请通过仓外 auth-audit.jsonl / access-log.jsonl 核查。",
          );
        } else {
          setError(`HTTP ${e.status}：${e.message}`);
        }
      } else {
        setError(String(e));
      }
    }
  }, []);

  useEffect(() => {
    if (devEnabled && current === null) return;
    void loadSessions();
  }, [current, devEnabled, loadSessions, sessionEpoch]);

  return (
    <section className="cases-page" aria-labelledby="admin-sessions-title">
      <div className="cases-page__head">
        <div>
          <h1 id="admin-sessions-title">会话与安全审计（P-12）</h1>
          <p className="hint">
            会话存储于独立 <code>session.db</code>（0700，严禁纳入数据备份 SD-14）；
            空闲超时 30m / 绝对超时 8h（AU-11 / AU-12）；只读入口越权写与身份绑定异常实时追加至仓外{" "}
            <code>access-log.jsonl</code>（C-103 / C-104）。
          </p>
        </div>
      </div>

      {error && (
        <div className="state state--warn" role="alert">
          <h2>审计访问说明</h2>
          <p>{error}</p>
        </div>
      )}

      <h2>安全与审计契约状态（SD-1…SD-18 / C-103 / C-104）</h2>
      <dl className="facts">
        <dt>Session Cookie 策略</dt>
        <dd>
          仅存 opaque 随机 ID（无 PII/claims），强制{" "}
          <code>HttpOnly + Secure + SameSite</code>（AU-3 / SD-1）
        </dd>
        <dt>双库物理隔离</dt>
        <dd>
          <code>session.db</code> 与 <code>projection.db</code> 独立 WAL；
          <code>session.db</code> 丢失仅触发全员重登與 Step-Up 失效，不影响 IR 与权威投影（SD-7…SD-15）
        </dd>
        <dt>C-103 只读入口审计</dt>
        <dd>
          对 <code>/api/v1/rules</code>、<code>/control-points</code>、<code>/routing</code>{" "}
          发起 POST/PUT/PATCH/DELETE 一律返 403 并写入{" "}
          <code>reason=read_only_entry</code>
        </dd>
        <dt>C-104 身份绑定审计</dt>
        <dd>
          生产模式缺 <code>open_id/tenant_id</code> 返 401（<code>identity_incomplete</code>）；
          模拟身份在生产模式一律返 403（<code>simulated_identity_in_production</code>）
        </dd>
      </dl>

      <h2>会话投影记录</h2>
      {sessions === null ? (
        <p className="hint">{error ? "当前身份或环境不展示在线会话表。" : "加载中…"}</p>
      ) : sessions.length === 0 ? (
        <div className="state">
          <p className="hint">当前会话投影集合为空（0 条记录）。</p>
        </div>
      ) : (
        <ul className="notrun">
          {sessions.map((s, idx) => (
            <li key={idx} className="font-data">
              {JSON.stringify(s)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
