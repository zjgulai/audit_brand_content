import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { appOrigin, reviewApi } from "../api/client";
import BrowserSupportNotice from "../components/BrowserSupportNotice";
import LoginQr from "../components/LoginQr";

/**
 * 登录页。
 *
 * ★ 2026-10-26 第三次重做。前两版的问题是**文案与信息密度**，不是配色：
 *   1. 页面上有大量解释性文字（「本工作台不单独维护账号密码」「授权范围仅包含…」
 *      「机器判定与人工意见分开记账…」），用户来这里是登录的，不是读说明的；
 *   2. 品牌栏里那句「品牌内容在对外发布之前，在这里过一遍合规」是装饰性文案，
 *      它不回答任何问题，只占版面。
 *
 *   现在只留三样：**产品名**、**一句它在做什么**、**登录动作**。
 *   其余全部移出第一屏（浏览器支持范围放进页脚一行小字，仍可见但不抢注意力）。
 *
 * ★ 设计约束（委托方 2026-10-26 十条）：
 *   · 颜色全部来自 Radix Colors（tokens.css 里的语义别名，本文件不写任何色值）；
 *   · 字号只用三档：--text-sm(12) / --text-base(14) / --text-title(18)；
 *   · 边框一律 0.5px；圆角只有面板 6px 与控件 4px 两档（嵌套同心）；
 *   · 没有阴影、没有左侧色条；过渡只有 250ms ease-out 且仅作用于颜色。
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
    <main className="login">
      <div className="login__panel">
        <div className="login__head">
          <div className="login__brand">
            {/* ★ 真实 Momcozy logo（momcozy.com 实测抓取）。不做 CSS 变形。 */}
            <img
              className="login__logo"
              src="/brand/logo.svg"
              alt="Momcozy"
              width="120"
            />
            <h1 className="login__name">内容审核工作台</h1>
          </div>
          <p className="login__lede">登录后处理待复核内容并提交结论。</p>
        </div>

        {state === "checking" && (
          <p className="login__status" role="status">
            正在确认登录状态
          </p>
        )}

        {state === "anon" && (
          <div className="login__signin">
            {/* ★★ 2026-10-30：撤掉账号口令表单，飞书扫码是**唯一**入口。
                委托方原话：「将账号密码 Daisy 去掉，依旧使用飞书扫码登陆作为登陆方」。
                上一版（2026-10-29）曾把口令表单放在主位、扫码放备选，
                理由是「测试便利」—— 代价是这条通道绕过飞书租户校验，
                任何知道口令的人都能进一个装着真实审计数据的系统。
                那条代价现在被撤回了；扫码本身就是真实的授权通道。

                ★ 后端 `POST /auth/password` 的实现仍留在 `api/production_app.py`，
                  但由 `REVIEW_PASSWORD_LOGIN` 控制且**默认关**、生产环境已置空 ——
                  于是该端点在生产上返 404，界面上没有任何入口指向它。
                  「界面上看不见」不等于「通道不存在」，所以真判据在环境变量与服务端
                  404 上，而不是这份 JSX。 */}
            <div className="login__alt login__alt--solo">
              <span className="login__alt-label">飞书扫码登录</span>
              <LoginQr target={`${appOrigin}/auth/login`} />
              <a
                className="btn login__sso"
                href={`${appOrigin}/auth/login`}
              >
                使用飞书账号登录
              </a>
            </div>
          </div>
        )}

        {state === "error" && (
          <div className="login__error" role="alert">
            <p className="login__error-title">无法确认登录状态</p>
            <p className="login__error-detail">{detail}</p>
            <p className="login__error-hint">
              后端暂时不可达，重新登录不会恢复。请稍后刷新。
            </p>
          </div>
        )}
      </div>

      {/* ★ 2026-10-29（#113）：原来这里是一行手写文案
          「仅支持桌面版 Chrome 155 及以上」—— 版本号**写死在组件里**，
          而基准在 `web/src/data/browser-baseline.json`（随时会更新）。
          手写那一行的后果：基准改了、这行不改，界面就在撒谎。

          换成组件后两件事一起解决：
            · 版本范围从 baseline 读（B3 要求的「不许写死」）；
            · 非支持浏览器会看到 role="alert" 的显式横幅（原来只有一行灰字）。 */}
      <div className="login__foot">
        {/* ★ 登录页是「第一次知道什么浏览器能用」的地方，所以这里常显范围；
            业务页面（AppShell）不传这个参数 —— 那里显示它就是噪音。 */}
        <BrowserSupportNotice alwaysShowRange />
      </div>
    </main>
  );
}
