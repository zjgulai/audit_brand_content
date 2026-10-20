import { NavLink, Outlet } from "react-router-dom";
import { useIdentity } from "./IdentitySwitcher";

export default function AppShell() {
  const {
    identities,
    current,
    switching,
    error,
    enable,
    switchTo,
  } = useIdentity();

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
          {__REVIEW_DEV_IDENTITY__ ? (
            identities.length === 0 ? (
              <button
                type="button"
                className="btn"
                disabled={switching}
                onClick={() => void enable()}
              >
                {switching ? "启用开发身份中…" : "启用本地开发身份"}
              </button>
            ) : (
              <label>
                开发身份：{" "}
                <select
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
            <span>只读 · 生产认证写入口未接入</span>
          )}
          {error && (
            <span className="error" role="alert">
              身份操作失败：{error}
            </span>
          )}
        </div>
      </header>
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
