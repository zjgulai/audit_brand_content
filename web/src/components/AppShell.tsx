import { useEffect, useState } from "react";
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useIdentity } from "./IdentitySwitcher";
import BrowserSupportNotice from "./BrowserSupportNotice";
import ErrorBoundary from "./ErrorBoundary";
import Button from "../ui/Button";
import Icon, { type IconName } from "../ui/icon";
import { reviewApi } from "../api/client";


/**
 * 全局外壳（2026-10-26 重做：横向顶栏 → 左侧可折叠侧边栏）。
 *
 * ## 为什么重做
 *
 * 上一版把 10 个导航项平铺在顶栏里。它在 1440px 下勉强一行，但：
 *   1. 宽度一窄就折行，而折行后「复核队 / 列」这种词中被切开的坏味道要靠
 *      `white-space: nowrap` 硬撑 —— 那是拿字号换布局，不是布局好；
 *   2. 顶栏本质是**状态栏**，塞满导航之后它既不能放页面标题，也不能放操作，
 *      于是每个页面只能自己再长一套标题区，全站层级不一致。
 *
 * 现在分成三层，与 `reddit.lute-tlz-dddd.top` 同构（但比它多两件事，见下）：
 *
 *   ┌──────────┬────────────────────────────────────┐
 *   │ 侧边栏   │ 顶栏（页面标题 + 全局操作）         │
 *   │ 品牌     ├────────────────────────────────────┤
 *   │ 分组导航 │ 主内容（暖底 + 卡片）              │
 *   │ 折叠     │                                    │
 *   │ 身份区   │                                    │
 *   └──────────┴────────────────────────────────────┘
 *
 * ★ 比参照站多做的两件事（不是为不同而不同，是被本项目的门禁逼出来的）：
 *   · 侧边栏折叠状态要**可判**：`data-collapsed` 落在 DOM 上，而不是只在 CSS 里
 *     消失，否则「折叠了没有」这件事没人量得到；
 *   · 导航项带 `aria-current`（NavLink 自动）与可见焦点环 —— 侧边栏比顶栏更容易
 *     丢焦点，因为它的可点区域是竖直的。
 *
 * ## 保留的契约（改布局不许破坏这些）
 *
 * · `.shell__right select` + `aria-label="切换本地开发身份"`：联调门禁靠它切身份；
 * · `.shell__nav a`：`check_pages.mjs` 的 SPA 内导航与几何断言走它；
 * · `.shell__main` + `#main`：跳过链接与 `tabIndex={-1}` 的落点；
 * · `.shell__footer`：五标签铁律那句话。
 */

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
}

interface NavGroup {
  caption: string;
  items: NavItem[];
}

/**
 * 导航分组。名字按**审核员一天里的动作**分，不按系统模块分。
 *
 * ★ 术语对照（业务听得懂）：
 *   复核队列 → 待人工复核（机器拿不准，等人判）
 *   案件总览 → 审核全景（查历史，不看待办）
 *   签发台   → 合规签发（正式放行）
 *   下线任务 → 违规下架（已发布的要召回）
 *   分类规范 → 规则词典（查某条规则是什么意思）
 */
const NAV_GROUPS: NavGroup[] = [
  {
    caption: "日常工作",
    items: [
      { to: "/submit", label: "审核工作台", icon: "sparkles" },
      { to: "/inbox", label: "待办收件箱", icon: "inbox" },
      { to: "/queue", label: "待人工复核", icon: "clock" },
      { to: "/cases", label: "审核全景", icon: "search" },
    ],
  },
  {
    caption: "合规处置",
    items: [
      { to: "/release", label: "合规签发", icon: "check-circle" },
      { to: "/takedown", label: "违规下架", icon: "shield-alert" },
      { to: "/appeals", label: "申诉复议", icon: "help-circle" },
      { to: "/reports", label: "合规报告", icon: "file-text" },
    ],
  },
  {
    caption: "知识与治理",
    items: [
      { to: "/taxonomy", label: "规则词典", icon: "layers" },
      { to: "/admin/grants", label: "授权治理", icon: "user-check" },
      { to: "/admin/sessions", label: "安全审计", icon: "history" },
    ],
  },
];

/**
 * 路由 → 顶栏标题。**唯一一处**，页面自己不再长标题区。
 *
 * ★★ 2026-10-26 两次踩到同一条：这里的 `sub` 是**常驻文案**，它在数据到之前
 *   就已经在 DOM 里了。而 `check_pages.mjs` 用 `waitBody("证据链")` /
 *   `waitBody("待审原件（ContentUnit）")` 这类词当「数据已到」的信号 ——
 *   一旦外壳里出现同一个词，那个等待就**恒成立**，读到的永远是「加载中…」。
 *   表现是「API 200 + 无 console 错误 + 页面永远加载中」，三个读数各自都对。
 *
 *   所以：**外壳文案不许复用数据区的词**（证据链 / 待审原件 / 对外标签 /
 *   覆盖证明 / 复核动作）。这条由 check_pages 的 `shellNoSignal` 反向对照守着。
 */
const PAGE_META: { match: (p: string) => boolean; icon: IconName; title: string; sub: string }[] = [
  { match: (p) => p === "/inbox", icon: "inbox", title: "待办收件箱", sub: "分派给你、或等待认领的案件" },
  { match: (p) => p === "/queue", icon: "clock", title: "待人工复核", sub: "机器拿不准的内容，需要你给出结论" },
  { match: (p) => p === "/cases", icon: "search", title: "审核全景", sub: "全部送审内容与它们当前的去向" },
  { match: (p) => p.startsWith("/cases/"), icon: "file-text", title: "案件详情", sub: "查看这一条内容的判定与处置" },
  { match: (p) => p === "/release", icon: "check-circle", title: "合规签发", sub: "确认无误后正式放行" },
  { match: (p) => p === "/takedown", icon: "shield-alert", title: "违规下架", sub: "已发布内容的召回与处置" },
  { match: (p) => p === "/appeals", icon: "help-circle", title: "申诉复议", sub: "业务方对结论有异议时的复审" },
  { match: (p) => p === "/reports", icon: "file-text", title: "合规报告", sub: "每一份判定与签发的书面留痕" },
  { match: (p) => p.startsWith("/reports/"), icon: "file-text", title: "报告详情", sub: "判定依据与签发记录的完整视图" },
  { match: (p) => p === "/taxonomy", icon: "layers", title: "规则词典", sub: "查一条规则管什么、依据是什么" },
  { match: (p) => p === "/admin/grants", icon: "user-check", title: "授权治理", sub: "谁能审哪些品线、谁批的" },
  { match: (p) => p === "/admin/sessions", icon: "history", title: "安全审计", sub: "登录与高风险动作的流水" },
  { match: (p) => p === "/submit", icon: "sparkles", title: "审核工作台", sub: "上传文件或输入文案，即刻生成合规审查结果" },
];

function metaFor(pathname: string): { icon: IconName; title: string; sub: string } {
  return (
    PAGE_META.find((m) => m.match(pathname)) ?? {
      icon: "sparkles",
      title: "内容审核工作台",
      sub: "机器先判、人来复核",
    }
  );
}

/** 身份区（生产）：姓名 + 退出。放在侧边栏底部，不占顶栏。 */
function ProductionIdentity() {
  const { current, error } = useIdentity();
  const navigate = useNavigate();

  if (error === "unauthorized") return <Navigate to="/login" replace />;
  if (!current) {
    return (
      <span className={error ? "error" : "hint"} role={error ? "alert" : undefined}>
        {error ? "身份读取失败" : "正在确认身份…"}
      </span>
    );
  }
  return (
    <div className="shell__identity">
      <span className="shell__identity-name" title={current.label}>
        {current.label}
      </span>
      <Button
        variant="ghost"
        onClick={() => {
          void (async () => {
            try {
              await reviewApi.logout();
            } catch {
              /* 登出失败也回登录页：session 可能已经失效 */
            }
            navigate("/login", { replace: true });
          })();
        }}
      >
        <Icon name="arrow-left" size={12} /> 退出
      </Button>
    </div>
  );
}

export default function AppShell() {
  const {
    identities,
    current,
    switching,
    error,
    sessionEpoch,
    enable,
    switchTo,
  } = useIdentity();
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return window.localStorage.getItem("review-workbench.sidebar-collapsed") === "1";
    } catch {
      return false;
    }
  });
  const location = useLocation();
  const meta = metaFor(location.pathname);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        "review-workbench.sidebar-collapsed",
        collapsed ? "1" : "0",
      );
    } catch {
      /* 隐私模式下 localStorage 会抛；折叠状态退化成「本次会话有效」即可 */
    }
  }, [collapsed]);

  useEffect(() => {
    if (!current) {
      setUnreadCount(0);
      return;
    }
    let alive = true;
    reviewApi
      .listNotifications()
      .then((list) => {
        if (!alive) return;
        setUnreadCount(list.filter((n) => n.unread !== false).length);
      })
      .catch(() => {
        if (alive) setUnreadCount(0);
      });
    return () => {
      alive = false;
    };
  }, [current, sessionEpoch]);

  return (
    <div
      className={"shell" + (collapsed ? " shell--collapsed" : "")}
      data-collapsed={collapsed ? "true" : "false"}
    >
      <a className="skip-link" href="#main">
        跳到主内容
      </a>

      {/* ── 侧边栏 ─────────────────────────────────────────────────── */}
      <aside className="shell__sidebar" aria-label="工作台导航">
        {/* ★ 2026-10-26：真实 Momcozy logo（momcozy.com 实测抓取，344×36，
           心形 + 文字标，主色 #6A2B3A）。
           ★ logo 不做任何 CSS 变形（不加阴影、不改长宽比、不缩放不可读）；
             只放原生尺寸，与「内容审核工作台」几个字同行。 */}
        <div className="shell__brand-wrap">
          <img
            className="shell__brand-logo"
            src="/brand/logo-mark.svg"
            alt="Momcozy"
            width="120"
          />
          <span className="shell__brand-sub">内容审核工作台</span>
          <button
            type="button"
            className="shell__collapse"
            onClick={() => setCollapsed((v) => !v)}
            aria-expanded={!collapsed}
            aria-label={collapsed ? "展开侧边栏" : "收起侧边栏"}
            title={collapsed ? "展开侧边栏" : "收起侧边栏"}
          >
            <Icon name={collapsed ? "chevron-right" : "chevron-left"} size={14} />
          </button>
        </div>

        <nav className="shell__nav" aria-label="主导航">
          {NAV_GROUPS.map((group) => (
            <div className="shell__nav-group" key={group.caption}>
              <p className="shell__nav-caption">{group.caption}</p>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    "shell__nav-item" + (isActive ? " is-active" : "")
                  }
                  title={collapsed ? item.label : undefined}
                >
                  <Icon name={item.icon} size={15} className="shell__nav-icon" />
                  <span className="shell__nav-label">{item.label}</span>
                  {item.to === "/inbox" && unreadCount > 0 && (
                    <span className="shell__nav-badge" aria-label={`${unreadCount} 条未读`}>
                      {unreadCount}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="shell__sidebar-foot">
          {__REVIEW_DEV_IDENTITY__ ? (
            identities.length === 0 ? (
              <Button
                variant="secondary"
                disabled={switching}
                onClick={() => void enable()}
              >
                {switching ? "启用开发身份中…" : "启用本地开发身份"}
              </Button>
            ) : (
              <label className="shell__dev-id">
                <span className="shell__nav-caption">开发身份</span>
                <select
                  data-identity-switch=""
                  value={current?.id ?? ""}
                  disabled={switching || current === null}
                  onChange={(event) => void switchTo(event.target.value)}
                  aria-label="切换本地开发身份"
                >
                  {current === null && <option value="">切换中…</option>}
                  {identities.map((identity) => (
                    <option key={identity.id} value={identity.id}>
                      {identity.label}（{identity.id}）
                    </option>
                  ))}
                </select>
              </label>
            )
          ) : (
            <ProductionIdentity />
          )}
          {error && (
            <span className="error" role="alert">
              身份操作失败：{error}
            </span>
          )}
        </div>
      </aside>

      {/* ── 顶栏 + 主内容 ──────────────────────────────────────────── */}
      <div className="shell__body">
        <header className="shell__header">
          {/* ★ 2026-10-26：这里**不是 h1**。
              每个页面自己有一个 h1（`.case h1` / `.cases-page h1` …），
              外壳再放一个就会变成「一页两个 h1」——
              a11y_check 的 h1-unique 在 15 条路由上全部报 count=2。
              外壳的标题是**路标**，不是文档标题，所以用 p + aria-labelledby 之外的语义。 */}
          <div className="shell__heading">
            <span className="shell__title-icon" aria-hidden="true">
              <Icon name={meta.icon} size={15} />
            </span>
            <div className="shell__heading-text">
              <p className="shell__title">{meta.title}</p>
              <p className="shell__subtitle">{meta.sub}</p>
            </div>
          </div>
          <div className="shell__right">
            {current && current.product_lines.length > 0 && (
              <span
                className="shell__scope-pill font-data"
                title={`授权产品线范围：${current.product_lines.join(" / ")}`}
              >
                品线 {current.product_lines.length}
              </span>
            )}
            {current && (
              <NavLink
                to="/inbox"
                className="shell__notif-badge"
                aria-label={`工作台通知：${unreadCount} 条未读`}
              >
                <Icon name="bell" size={13} /> {unreadCount}
              </NavLink>
            )}
          </div>
        </header>

        <main id="main" className="shell__main" tabIndex={-1}>
          {/* ★ #113 / TS-12：非支持浏览器的显式告知横幅。
              ★ 只告知、不阻断 —— 详情见 BrowserSupportNotice 文件头第 3 条。 */}
          <BrowserSupportNotice />
          {__REVIEW_DEV_IDENTITY__ && switching ? (
            <section className="case" aria-live="polite">
              <h1>正在切换开发身份</h1>
              <p>旧身份的案件内容已隐藏；新 session 建立后重新加载。</p>
            </section>
          ) : (
            /* ★ ADR-0021 · W-3：路由级错误边界。
               改前全仓 ErrorBoundary = 0 命中 —— 任意页面一个渲染异常就整站白屏。

               ★ 为什么挂在 Outlet 上而不是逐条路由包：
                 19 条路由逐条包，漏一条就是一个白屏缺口，而「漏了哪条」
                 没有任何东西会告诉你。挂在这里一次覆盖全部。

               ★ 为什么 key={location.pathname}：换页时把边界重置。
                 不重置的话，从崩掉的 A 页跳到正常的 B 页，B 页看到的还是
                 A 页的错误页 —— 用户会以为 B 也坏了。
                 location 是这个组件里已有的，不额外引入依赖。 */
            <ErrorBoundary name={`route:${location.pathname}`} key={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          )}
        </main>
      </div>
    </div>
  );
}
