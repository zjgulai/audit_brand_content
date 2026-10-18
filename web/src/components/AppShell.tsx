import { NavLink, Outlet } from "react-router-dom";
import { apiBase } from "../api/client";

export default function AppShell() {
  return (
    <div className="shell">
      <header className="shell__header">
        <strong>内容审查工作台</strong>
        <nav>
          <NavLink to="/queue">复核队列</NavLink>
          <NavLink to="/login">登录</NavLink>
        </nav>
        <span className="shell__api">API：{apiBase}</span>
      </header>
      <main className="shell__main">
        <Outlet />
      </main>
      <footer className="shell__footer">
        阶段一 Web 只读：不提供签发 / 撤回 / 发布入口。
      </footer>
    </div>
  );
}
