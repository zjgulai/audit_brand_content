import { NavLink, Outlet } from "react-router-dom";
import { useIdentity } from "./IdentitySwitcher";

export default function AppShell() {
  const { identities, current, unavailable, switching, error, switchTo } = useIdentity();

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        跳到主内容
      </a>
      <header className="shell__header">
        <span className="shell__brand">内容审核工作台</span>
        <nav aria-label="主导航">
          <NavLink to="/queue">复核队列</NavLink>
          <NavLink to="/taxonomy">分类规范</NavLink>
        </nav>
        <div className="shell__right">
          {unavailable ? (
            <span title="后端未提供 /dev/session，本机联调入口未启用">
              身份：不可用
            </span>
          ) : (
            <label>
              身份：{" "}
              <select
                value={current?.id ?? ""}
                disabled={switching || identities.length === 0}
                onChange={(e) => void switchTo(e.target.value)}
                aria-label="切换本地开发身份"
              >
                {identities.length === 0 && <option value="">加载中…</option>}
                {identities.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.label}（{i.id}）
                  </option>
                ))}
              </select>
            </label>
          )}
          {error && <span className="error">切换失败：{error}</span>}
        </div>
      </header>
      <main id="main" className="shell__main" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="shell__footer">
        判定由后端唯一产出，本页不重算；人工动作只经写 API；五标签一律止于「待放行」。
      </footer>
    </div>
  );
}
