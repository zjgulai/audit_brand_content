import { useCallback, useEffect, useState } from "react";
import { ApiError, request } from "../api/client";
import { useIdentity } from "../components/IdentitySwitcher";
import LoadingRows from "../components/LoadingRows";

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
            "仅内部治理角色可访问会话与安全审计。",
          );
        } else if (e.status === 404) {
          setError(
            "生产环境不提供在线会话枚举，请到服务器上的 auth-audit.jsonl 与 access-log.jsonl 核查。",
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
          <h1 id="admin-sessions-title">安全审计</h1>
          <p className="hint">
            查看登录会话策略与安全审计日志说明。
          </p>
        </div>
      </div>

      {error && (
        <div className="state state--warn" role="alert">
          <h2>审计访问说明</h2>
          <p>{error}</p>
        </div>
      )}

      <h2>安全与审计策略</h2>
      <dl className="facts">
        <dt>会话凭证保护</dt>
        <dd>仅保存随机句柄，不含个人敏感信息，启用严格同源与加密传输保护</dd>
        <dt>会话有效期</dt>
        <dd>空闲 30 分钟或连续登录 8 小时后需重新验证身份</dd>
        <dt>规则只读保护</dt>
        <dd>网页端不直接修改审核规则与路由配置，越权请求自动拦截并记入审计日志</dd>
        <dt>企业身份核验</dt>
        <dd>生产环境强制校验飞书企业身份与租户归属</dd>
      </dl>

      <h2>在线会话记录</h2>
      {sessions === null ? (
        <LoadingRows rows={3} label="正在加载会话记录" />
      ) : sessions.length === 0 ? (
        <div className="state">
          <p className="hint">当前无在线会话记录。</p>
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
