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
  // ★ 2026-10-29：账号密码登录（委托方要求，为测试便利）。
  //   只有「显式发起提交」时才显示它的错误 —— 页面刚打开就红一片会让人
  //   以为登录坏了，而那只是还没填。
  const [pwUser, setPwUser] = useState("");
  const [pwSecret, setPwSecret] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwError, setPwError] = useState("");

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
            {/* ★★ 2026-10-29：主入口改成账号密码（委托方要求，测试便利）。
                飞书扫码保留为备选 —— 它是真实授权通道，删掉就没有
                租户校验那条路了。 */}
            <form
              className="login__form"
              onSubmit={async (e) => {
                e.preventDefault();
                if (pwBusy) return;
                setPwBusy(true);
                setPwError("");
                try {
                  await reviewApi.passwordLogin(pwUser, pwSecret);
                  // 成功后整页跳 —— 让它走一次真实的「带 session 重新加载」，
                  // 而不是在页面里改状态。后者会绕过 identity provider 的
                  // 初始化路径，于是侧栏身份、权限都不刷新。
                  window.location.assign("/queue");
                } catch (err) {
                  const e2 = err as { status?: number; message?: string };
                  // ★ 404 = 这个部署没开密码登录。必须与「密码错」分开说，
                  //   否则用户会一直重试一个根本不存在的口令。
                  setPwError(
                    e2.status === 404
                      ? "本部署未启用账号密码登录，请用飞书扫码。"
                      : e2.status === 401
                        ? "账号或口令不正确。"
                        : `登录失败：${e2.message ?? "未知错误"}`,
                  );
                } finally {
                  setPwBusy(false);
                }
              }}
            >
              <label className="login__field">
                <span>账号</span>
                <input
                  type="text"
                  name="username"
                  autoComplete="username"
                  value={pwUser}
                  onChange={(e) => setPwUser(e.target.value)}
                  required
                />
              </label>
              <label className="login__field">
                <span>口令</span>
                <input
                  type="password"
                  name="password"
                  autoComplete="current-password"
                  value={pwSecret}
                  onChange={(e) => setPwSecret(e.target.value)}
                  required
                />
              </label>
              <button
                type="submit"
                className="btn btn--primary login__submit"
                disabled={pwBusy || !pwUser || !pwSecret}
              >
                {pwBusy ? "登录中…" : "登录"}
              </button>
              {pwError && (
                <p className="login__form-error" role="alert">
                  {pwError}
                </p>
              )}
            </form>

            <div className="login__alt">
              <span className="login__alt-label">或</span>
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
