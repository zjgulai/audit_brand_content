import { useEffect, useState } from "react";
import QRCode from "qrcode";

/**
 * 登录二维码（2026-10-23）。
 *
 * ## 它编码什么
 *
 * **后端 `/auth/login` 的完整 URL** —— 与页面上那个「使用飞书账号登录」按钮
 * 是**同一个目标**，不是第二套登录流程。点按钮 = 浏览器整页跳过去；
 * 扫码 = 手机打开同一个地址，在飞书里完成授权。
 *
 * ## 它不做什么（重要，别让 UI 暗示超出口径）
 *
 * 飞书 OAuth 是「浏览器跳转 → 回调写 cookie」的流程，**没有反向通道**。
 * 所以手机扫码完成授权之后，**桌面浏览器不会自动登录** —— 桌面要单独再点一次按钮。
 * 页面上必须写清楚这一点，否则就是给用户一个假的「扫完就进去了」的承诺。
 * 要做桌面自动登录，需要后端起一套 ticket 签发/轮询/认领（本组件不属于那个方案）。
 *
 * ## 为什么用 SVG 而不是 canvas
 *
 *   · 不需要 `getContext`，在 SSG / 测试环境里也能生成；
 *   · 矢量，任何 DPR 下都清晰；
 *   · **可以直接被自动化脚本读回来做 round-trip 验证**
 *     （`web/scripts/check_login_qr.mjs` 用 jsqr 解码，断言解出的字符串
 *      逐字等于这里给的 URL —— 没有这条，画出来的东西是不是真能扫，没人知道）。
 *
 * ★ 编码调用是异步的（qrcode 库的 `toString` 返回 Promise），
 *   所以这里必须处理「还没生成好」与「生成失败」两态，不能直接渲染一个空框。
 */

export interface LoginQrProps {
  /** 要编码的完整 URL；调用方传 `${appOrigin}/auth/login`。 */
  target: string;
  /** 二维码边长（CSS px）。默认 132。 */
  size?: number;
}

export default function LoginQr({ target, size = 132 }: LoginQrProps) {
  const [markup, setMarkup] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setMarkup(null);
    setFailed(null);
    QRCode.toString(target, {
      type: "svg",
      errorCorrectionLevel: "M",
      margin: 1,
      width: size,
      color: { dark: "#35141a", light: "#ffffff" },
    })
      .then((svg) => {
        if (alive) setMarkup(svg);
      })
      .catch((e: unknown) => {
        if (alive) setFailed(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
  }, [target, size]);

  if (failed) {
    // 生成失败就说生成失败 —— 不要留一个空白方块让人以为「扫不出来是网络问题」。
    return (
      <p className="login__qr-failed hint" role="alert">
        二维码生成失败（{failed}）。请直接点右侧的「使用飞书账号登录」。
      </p>
    );
  }

  if (markup === null) {
    return <p className="login__qr-pending hint">正在生成二维码…</p>;
  }

  return (
    <div className="login__qr">
      <div
        className="login__qr-code"
        // qrcode 库自产的 SVG，内容只由 target 决定（不含外部引用）。
        // 用 dangerouslySetInnerHTML 是必要的：它是字符串形式的 SVG，
        // 而这里的输入是**我们自己给的常量 URL**，不是用户输入。
        dangerouslySetInnerHTML={{ __html: markup }}
      />
      {/* ★ 2026-10-26：原来三句（扫一扫 / 手机上完成 / 桌面仍需点按钮）。
          前两句是重复的，第三句是「按钮就在旁边」这件事的要说明 —— 都删。
          只留「手机扫码」这个用户真正需要知道的信息。 */}
      <p className="login__qr-note">手机飞书扫码</p>
    </div>
  );
}
