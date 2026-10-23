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
 *
 * ★ 2026-10-23 视觉校验重做：此前本页只有 `<h1>登录</h1>` + 三行字，是全站唯一
 *   一个不带任何产品标识、没有卡片、也没有失败兜底的页面 —— 生产 500 时整页只剩
 *   一行红字，读起来像「没做」。现在补齐：
 *   1. 产品标识与一句话说明（这是什么系统、登录后能做什么）；
 *   2. 一张登录卡（主行动 = 飞书 SSO，明确写出会跳转外部）；
 *   3. 三种态各有自己的视觉：检查中 / 未登录 / 读取失败（失败**不**提供假的登录按钮，
 *      而是说明「当前无法确认登录状态」，避免把网络故障当成「请重新登录」）；
 *   4. 页脚保留五标签铁律与浏览器支持范围。
 */

type LoginState = "checking" | "anon" | "authed" | "error";

export default function LoginPage() {
  const [state, setState] = useState<LoginState>(
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
    <main id="main" className="login">
      {/* 封面装饰层：纯 CSS 绘制，无位图、无外链、不阻塞首屏。
          与 lute-tlz-dddd.top 的封面同构（点阵 + 斜向信号线 + 光扫过），
          但配色改用本项目的 L1 token，不引入第二个品牌色板。 */}
      <div className="login__cover" aria-hidden="true">
        <span className="login__cover-grid" />
        <span className="login__cover-sweep" />
        <span className="login__cover-line login__cover-line--1" />
        <span className="login__cover-line login__cover-line--2" />
        <span className="login__cover-line login__cover-line--3" />
      </div>

      <div className="login__shell">
        <header className="login__masthead">
          <div className="login__brand">
            <span className="login__mark" aria-hidden="true" />
            <div>
              <p className="login__product">内容审核工作台</p>
              <p className="login__tagline">
                机器先判、人来复核。登录后可处理复核队列、审阅证据链并提交正式复核结论。
              </p>
            </div>
          </div>
          <span className="login__kicker font-data">CONTENT REVIEW · DP3/DP4</span>
        </header>

        <div className="login__card">
          <div className="login__divider" role="presentation" />

          {state === "checking" && (
            <p className="login__status" role="status">
              正在确认登录状态…
            </p>
          )}

          {state === "anon" && (
            <div className="login__action">
              <p className="login__lead">
                本工作台不单独维护账号密码，统一使用飞书身份登录。
              </p>
              <a className="btn btn--primary login__sso" href={`${appOrigin}/auth/login`}>
                使用飞书账号登录
              </a>
              <p className="login__note">
                将跳转到飞书完成授权，返回后自动进入复核队列。授权范围仅包含读取你的
                飞书身份与所在租户，不读取聊天内容。
              </p>
            </div>
          )}

          {state === "error" && (
            <div className="login__action">
              <p className="login__lead login__lead--error" role="alert">
                当前无法确认登录状态：{detail}
              </p>
              <p className="login__note">
                这通常说明工作台后端暂时不可达，<strong>不是账号问题</strong>，
                重新登录也不会恢复。请稍后刷新；若持续失败，请联系项目统筹并提供上面的错误信息。
              </p>
            </div>
          )}
        </div>

        <footer className="login__footer">
          <BrowserSupportNotice />
          <p className="login__note">
            机器判定与人工意见分开记账：人工意见不改变机器标签，也不等于放行；
            对外五标签一律止于「待放行」。
          </p>
        </footer>
      </div>
    </main>
  );
}
