import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useIdentity } from "./IdentitySwitcher";
import Button from "../ui/Button";
import Icon from "../ui/icon";
import { reviewApi } from "../api/client";

const SubmitPage = lazy(() => import("../pages/SubmitPage"));

/**
 * 全局外壳（Wave B / C / D / E · 落 G-01 & G-04 12 页全量架构）。
 *
 * 1. 保留 `.shell__header nav a`、`.shell__right select`、`select[aria-label="切换本地开发身份"]`
 *    等全部现有联调门禁选择器；
 * 2. 主导航覆盖全部核心工作台模块：
 *    收件箱 (/inbox) · 复核队列 (/queue) · 案件总览 (/cases) · 申诉 (/appeals) ·
 *    签发台 (/release) · 下线 (/takedown) · 报告 (/reports) · 分类规范 (/taxonomy) ·
 *    授权治理 (/admin/grants) · 安全审计 (/admin/sessions)；
 * 3. 顶栏右侧提供「+ 提交审查」全局快捷抽屉（同时支持独立路由 /submit）、In-App 通知铃与身份区。
 */
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
    <>
      <span>{current.label}</span>
      <Button
        variant="secondary"
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
        退出登录
      </Button>
    </>
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
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);

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
    <div className="shell">
      <a className="skip-link" href="#main">
        跳到主内容
      </a>
      <header className="shell__header">
        <span className="shell__brand">内容审核工作台</span>
        <nav aria-label="主导航">
          <NavLink to="/inbox">收件箱</NavLink>
          <NavLink to="/queue">复核队列</NavLink>
          <NavLink to="/cases">案件总览</NavLink>
          <NavLink to="/appeals">申诉中心</NavLink>
          <NavLink to="/release">签发台</NavLink>
          <NavLink to="/takedown">下线任务</NavLink>
          <NavLink to="/reports">报告索引</NavLink>
          <NavLink to="/taxonomy">分类规范</NavLink>
          <NavLink to="/admin/grants">授权治理</NavLink>
          <NavLink to="/admin/sessions">安全审计</NavLink>
        </nav>
        <div className="shell__right">
          {current && current.product_lines.length > 0 && (
            <span className="shell__scope-pill font-data" title="授权产品线范围">
              品线：{current.product_lines.join(" / ")}
            </span>
          )}
          <Button
            variant="secondary"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(!drawerOpen)}
          >
            <Icon name="plus" size={11} /> 提交审查
          </Button>
          {current && (
            <NavLink
              to="/inbox"
              className="shell__notif-badge"
              aria-label={`工作台通知：${unreadCount} 条未读`}
            >
              <Icon name="bell" size={12} /> 通知（{unreadCount}）
            </NavLink>
          )}
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
              <label>
                开发身份：{" "}
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
      </header>

      {drawerOpen && (
        <div
          className="submit-drawer-backdrop"
          role="dialog"
          aria-modal="false"
          aria-label="快速提交内容审查抽屉"
        >
          <div className="submit-drawer-panel">
            <Suspense fallback={<p className="hint">加载提交单…</p>}>
              <SubmitPage
                embeddedInDrawer
                onCloseDrawer={() => setDrawerOpen(false)}
              />
            </Suspense>
          </div>
        </div>
      )}

      <main id="main" className="shell__main" tabIndex={-1}>
        {__REVIEW_DEV_IDENTITY__ && switching ? (
          <section className="case" aria-live="polite">
            <h1>正在切换开发身份</h1>
            <p>旧身份的案件内容已隐藏；新 session 建立后重新加载。</p>
          </section>
        ) : (
          <Outlet />
        )}
      </main>
      <footer className="shell__footer">
        判定由后端唯一产出，本页不重算；人工动作只经写 API；五标签一律止于「待放行」。
      </footer>
    </div>
  );
}
