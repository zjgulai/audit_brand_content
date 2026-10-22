import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { appOrigin, reviewApi } from "../api/client";
import BrowserSupportNotice from "../components/BrowserSupportNotice";

/**
 * 登录页（T-150 + #113 / TS-12 浏览器范围明示）。
 *
 * 生产：后端 `/auth/login` 发起飞书 OAuth；回调后 `csrf` 与 session cookie 由服务端下发。
 * 开发：身份来自 `/dev/session`（只在 dev wrapper 存在），本页直接回队列，
 *       **不把任何 dev 身份逻辑带进这里**。
 */
export default function LoginPage() {
  const [state, setState] = useState<"checking" | "anon" | "authed" | "error">(
    __REVIEW_DEV_IDENTITY__ ? "authed" : "checking",
  );
  const [detail, setDetail] = useState("");

  useEffect(() => {
    if (__REVIEW_DEV_IDENTITY__) return;
    let alive = true;
    reviewApi
      .me()
      .then(() => {
        if (alive) setState("authed");
      })
      .catch((e: unknown) => {
        if (!alive) return;
        const err = e as { status?: number; message?: string };
        if (err.status === 401) setState("anon");
        else {
          setState("error");
          setDetail(err.message ?? String(e));
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  if (state === "authed") return <Navigate to="/queue" replace />;

  return (
    <main id="main" className="case">
      <section>
        <h1>登录</h1>
        <BrowserSupportNotice />
        {state === "checking" && <p className="hint">正在检查登录状态…</p>}
        {state === "anon" && (
          <>
            <p>使用飞书账号登录后即可进入复核队列。</p>
            <p>
              <a className="btn" href={`${appOrigin}/auth/login`}>
                使用飞书登录
              </a>
            </p>
          </>
        )}
        {state === "error" && (
          <p className="error" role="alert">
            无法确认登录状态：{detail}
          </p>
        )}
      </section>
    </main>
  );
}
