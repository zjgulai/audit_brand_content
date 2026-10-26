import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { appOrigin, reviewApi } from "../api/client";
import BrowserSupportNotice from "../components/BrowserSupportNotice";
import LoginQr from "../components/LoginQr";

/**
 * 登录页（T-150 + #113 / TS-12 浏览器范围明示）。
 *
 * 生产：后端 `/auth/login` 发起飞书 OAuth；回调后 `csrf` 与 session cookie 由服务端下发。
 * 开发：身份来自 `/dev/session`（只在 dev wrapper 存在），本页直接回队列，
 *       **不把任何 dev 身份逻辑带进这里**。
 *
 * ★ 2026-10-26 第二次重做：**这一页此前与登录后的工作台完全不像同一个产品。**
 *
 *   委托方的原话是「ca.luteos.com 没有任何变化，我要的侧边栏什么都没有」——
 *   他打开的就是这一页（未登录时 /queue 会回落到 /login），而前两轮改的都是
 *   登录**之后**的 AppShell。于是「改了但看不到」= 改了等于没改。
 *
 *   现在这一页与 AppShell 共用同一套骨架：
 *     · 左侧品牌栏（同款 M 徽标 + Momcozy / 内容审核工作台），窄屏收起；
 *     · 右侧暖底内容区，卡片同款圆角与描边；
 *     · 页面标题、副标题、行动按钮的层级与登录后一致。
 *   这样「登录前」与「登录后」是同一个产品的两个状态，而不是两个网站。
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
    <div className="login">
      {/* 左侧品牌栏：与工作台侧边栏同宽同色，让「登录前/后」是同一个产品 */}
      <aside className="login__rail" aria-hidden="true">
        <div className="login__rail-brand">
          <span className="shell__brand-badge">M</span>
          <div className="login__rail-text">
            <span className="login__rail-name">Momcozy</span>
            <span className="login__rail-sub">内容审核工作台</span>
          </div>
        </div>
        <p className="login__rail-note">
          品牌内容在对外发布之前，
          <br />
          在这里过一遍合规。
        </p>
      </aside>

      <div className="login__body">
        <header className="login__head">
          <p className="login__kicker">待登录</p>
          <h1 className="login__title">登录内容审核工作台</h1>
          <p className="login__subtitle">
            机器先判、人来复核。登录后可以处理待复核内容、查看判定依据、提交正式结论。
          </p>
        </header>

        <div className="login__card">
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
              {/* ★ 扫码与按钮**同一个目标**（${appOrigin}/auth/login）。
                  扫码在手机上完成授权，桌面仍需点一次按钮 —— 飞书 OAuth 没有
                  反向通道，页面上必须写清楚，不能暗示「扫完桌面自动进入」。 */}
              <div className="login__signin">
                <LoginQr target={`${appOrigin}/auth/login`} />
                <div className="login__signin-actions">
                  <a
                    className="btn btn--primary login__sso"
                    href={`${appOrigin}/auth/login`}
                  >
                    使用飞书账号登录
                  </a>
                  <p className="login__note">
                    点击后会跳到飞书完成授权，同意之后自动回到工作台。
                    我们只读取你的飞书身份和所在租户，<strong>不读聊天内容</strong>。
                  </p>
                </div>
              </div>
            </div>
          )}

          {state === "error" && (
            <div className="login__action">
              <p className="login__lead login__lead--error" role="alert">
                现在无法确认你的登录状态：{detail}
              </p>
              <p className="login__note">
                这通常说明工作台后端暂时连不上，<strong>不是你的账号有问题</strong>，
                重新登录也不会好。请稍后刷新；如果一直这样，把上面这行错误发给项目统筹。
              </p>
            </div>
          )}
        </div>

        <footer className="login__foot">
          <BrowserSupportNotice />
          <p className="login__note">
            机器判定与人工意见分开记账：人工意见不改变机器标签，也不等于放行；
            对外五标签一律止于「待放行」。
          </p>
        </footer>
      </div>
    </div>
  );
}
