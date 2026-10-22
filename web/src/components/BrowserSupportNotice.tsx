import browserBaselineJson from "../data/browser-baseline.json";

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
}

export default function BrowserSupportNotice({
  userAgent,
  baseline = browserBaseline,
  compact = false,
}: BrowserSupportNoticeProps) {
  const ua =
    userAgent ??
    (typeof navigator !== "undefined" ? navigator.userAgent : "");
  const check = evaluateUserAgent(ua, baseline);
  const rangeText = formatSupportedBrowserRange(baseline);

  return (
    <div className="browser-support" data-browser-support="">
      <span className="hint" data-browser-range="">
        {rangeText}
      </span>
      {!check.supported && (
        <div
          className="state state--warn"
          role="alert"
          data-browser-unsupported-banner=""
        >
          <strong>
            当前浏览器不在正式支持范围（{check.reason}）
          </strong>
          {!compact && (
            <p className="hint">
              请更换为桌面版 Google Chrome {baseline.min_supported_chrome_major} 或{" "}
              {baseline.measured_chrome_major}。
              注意：本提示仅做告知、不阻断页面访问，在非支持浏览器下继续操作仍可能发生未预期的功能降级或异常。
            </p>
          )}
        </div>
      )}
    </div>
  );
}
