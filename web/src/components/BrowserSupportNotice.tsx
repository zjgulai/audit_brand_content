import browserBaselineJson from "../data/browser-baseline.json";
import { noticeModeFor } from "./browserNotice.logic";

/**
 * 浏览器支持范围明示与非支持环境检测横幅（#113 / TS-12）。
 *
 * 1. 版本范围动态读取自机器可读基准 `web/src/data/browser-baseline.json`，
 *    严禁在组件内写死静态 Chrome 版本号；
 * 2. 对 Safari、Edge、Firefox、移动端 UA 或低于 `min_supported_chrome_major` 的 Chrome，
 *    渲染 `role="alert"` 的显式「不支持」横幅；对受支持的桌面 Chrome 不渲染告警横幅；
 * 3. ★ 诚实性边界声明：本横幅只做显式告警提示、**不阻断**用户继续点击或请求 API，
 *    因此非支持浏览器下的「静默出错/功能异常」在运行时仍可能发生，绝不把横幅冒充为功能级降级。
 */

export interface BrowserBaseline {
  schema_version: number;
  policy_id: string;
  browser_family: string;
  window_size_majors: number;
  measured_chrome_version: string;
  measured_chrome_major: number;
  min_supported_chrome_major: number;
  supported_chrome_majors: number[];
  measured_at: string;
  max_age_days: number;
  measured_by: {
    command: string;
    stdout: string;
    platform: string;
    session?: string;
  };
  enforcement_mode: string;
  enforcement_honesty_note: string;
}

export const browserBaseline = browserBaselineJson as BrowserBaseline;

export function formatSupportedBrowserRange(
  baseline: Pick<
    BrowserBaseline,
    "min_supported_chrome_major" | "measured_chrome_major" | "measured_at"
  > = browserBaseline,
): string {
  return `正式支持范围：仅桌面 Google Chrome 最近两个主要版本（Chrome ${baseline.min_supported_chrome_major} / ${baseline.measured_chrome_major}，基准实测于 ${baseline.measured_at}）`;
}

export interface BrowserCheckResult {
  supported: boolean;
  reason: string | null;
  detectedFamily: string;
  detectedMajor: number | null;
}

export function evaluateUserAgent(
  ua: string,
  baseline: Pick<
    BrowserBaseline,
    "min_supported_chrome_major" | "measured_chrome_major"
  > = browserBaseline,
): BrowserCheckResult {
  const raw = (ua || "").trim();
  if (!raw) {
    return {
      supported: false,
      reason: "无法识别浏览器 User-Agent",
      detectedFamily: "Unknown",
      detectedMajor: null,
    };
  }
  if (/Mobile|Android|iPhone|iPad|iPod/i.test(raw)) {
    return {
      supported: false,
      reason: "移动端浏览器不在正式支持范围内",
      detectedFamily: "Mobile",
      detectedMajor: null,
    };
  }
  if (/Edg\/|EdgA\/|EdgiOS\//i.test(raw)) {
    return {
      supported: false,
      reason: "Microsoft Edge 不在正式支持范围内",
      detectedFamily: "Edge",
      detectedMajor: null,
    };
  }
  if (/OPR\/|Opera/i.test(raw)) {
    return {
      supported: false,
      reason: "Opera 不在正式支持范围内",
      detectedFamily: "Opera",
      detectedMajor: null,
    };
  }
  if (/Firefox\/|FxiOS\//i.test(raw)) {
    return {
      supported: false,
      reason: "Mozilla Firefox 不在正式支持范围内",
      detectedFamily: "Firefox",
      detectedMajor: null,
    };
  }
  const chromeMatch = raw.match(/(?:Headless)?Chrome\/(\d+)/);
  if (!chromeMatch) {
    if (/Safari\//i.test(raw)) {
      return {
        supported: false,
        reason: "Apple Safari 不在正式支持范围内",
        detectedFamily: "Safari",
        detectedMajor: null,
      };
    }
    return {
      supported: false,
      reason: "非桌面 Google Chrome 浏览器",
      detectedFamily: "Other",
      detectedMajor: null,
    };
  }
  const major = Number.parseInt(chromeMatch[1], 10);
  if (
    Number.isNaN(major) ||
    major < baseline.min_supported_chrome_major
  ) {
    return {
      supported: false,
      reason: `当前 Chrome 主版本（${major}）低于最低支持版本 Chrome ${baseline.min_supported_chrome_major}`,
      detectedFamily: "Chrome",
      detectedMajor: Number.isNaN(major) ? null : major,
    };
  }
  return {
    supported: true,
    reason: null,
    detectedFamily: "Chrome",
    detectedMajor: major,
  };
}

export interface BrowserSupportNoticeProps {
  userAgent?: string;
  baseline?: BrowserBaseline;
  compact?: boolean;
  /**
   * 即使在受支持的浏览器上，也渲染一行**极轻**的范围说明。
   *
   * ★ 只给登录页用（`LoginPage.tsx` 的页脚）。那是用户第一次接触系统、
   *   最该知道「什么浏览器能用」的地方，写在那里是**信息**；
   *   而把它挂到每个业务页面的正文顶部就是**噪音** ——
   *   2026-10-29 实测：它占掉工作区最显著的一行，把当前任务往下压。
   *   业务页面一律用默认值 `false`。
   */
  alwaysShowRange?: boolean;
}

export default function BrowserSupportNotice({
  userAgent,
  baseline = browserBaseline,
  compact = false,
  alwaysShowRange = false,
}: BrowserSupportNoticeProps) {
  const ua =
    userAgent ??
    (typeof navigator !== "undefined" ? navigator.userAgent : "");
  const check = evaluateUserAgent(ua, baseline);
  const rangeText = formatSupportedBrowserRange(baseline);

  // ★★★ 2026-10-29 修正一处**我自己造成的 UI 退化**，两个版本都留着。
  //
  //   改前：无条件渲染 `rangeText`（「正式支持范围：仅桌面 Google Chrome
  //   最近两个主要版本（Chrome 155 / 156，基准实测于 2026-10-23）」），
  //   于是**每一个业务页面的正文顶部都常驻那一行灰字**。
  //   实测截图：它横在标题栏与内容之间，把「待人工复核」这类当前任务
  //   往下压一整行，而 `.browser-support` / `.hint` / `.state--warn`
  //   三个类**根本没有样式定义**，所以是一行裸 div。
  //
  //   为什么错：受支持的浏览器**不需要被告知它被支持**。那条信息
  //   属于「不合规环境」的告知，不是常驻横幅。#113 的要求是
  //   「范围明示 + 非支持环境检测」，两者都不要求对合规用户常驻显示。
  //
  //   现在：
  //   · 受支持 → **渲染 null**（DOM 里没有它，零占位）；
  //   · 不受支持 → 渲染 role="alert" 横幅，把范围与原因一起说清
  //     （那才是真正需要看到它的时刻）。
  //
  //   ★ 范围明示没有消失：它落在登录页页脚 —— 那是用户第一次接触系统、
  //     最该知道「什么浏览器能用」的地方。业务页面里再重复一遍是噪音。
  // ★ 判据抽到 `browserNotice.logic.ts` 的真身里 —— 门禁 `check_browser_scope.mjs`
  //   直接 import 它喂真实入参，而不是正则扫这段源码。
  //   「源码里有 return null」这种判据在有注释的地方恒真（§2.4）。
  const mode = noticeModeFor({ supported: check.supported, alwaysShowRange });

  if (mode === "none") return null;

  if (mode === "range-only") {
    // 登录页专用：一行灰字，不带告警框、不带 role="alert"（没有告警）。
    return (
      <p className="hint" data-browser-support-range-only="">
        {rangeText}
      </p>
    );
  }

  return (
    <div className="browser-support" data-browser-support="">
      <div
        className="state state--warn"
        role="alert"
        data-browser-unsupported-banner=""
      >
        <strong>
          当前浏览器不在正式支持范围（{check.reason}）
        </strong>
        <p className="hint" data-browser-range="">
          {rangeText}
        </p>
        {!compact && (
          <p className="hint">
            请更换为桌面版 Google Chrome {baseline.min_supported_chrome_major} 或{" "}
            {baseline.measured_chrome_major}。
            注意：本提示仅做告知、不阻断页面访问，在非支持浏览器下继续操作仍可能发生未预期的功能降级或异常。
          </p>
        )}
      </div>
    </div>
  );
}
