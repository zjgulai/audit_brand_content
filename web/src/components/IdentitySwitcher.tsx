import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiBase } from "../api/client";

/**
 * 本地开发身份切换器。
 *
 * ★ 边界：只存在于本地联调（后端端点 `POST /dev/session` 只在
 *   `web/scripts/review_api_dev.py` 里，生产入口 `api/review_api.py` 没有它）。
 *
 * 它解决的是一个具体问题：复核动作要认出 principal，而飞书 OAuth（T-1）未接、
 * `LoginPage` 至今是占位。没有它，界面上「认领」按钮只能假装能点。
 *
 * 它**不是**登录：不保存凭据，不校验密码；服务端只接受已有的几个 principal id。
 */

export interface Identity {
  id: string;
  label: string;
  roles: string[];
  product_lines: string[];
}

interface IdentityState {
  identities: Identity[];
  current: Identity | null;
  /** 后端未提供 /dev 端点（例如接了生产入口）时为 true */
  unavailable: boolean;
  switching: boolean;
  error: string | null;
  switchTo: (id: string) => Promise<void>;
}

const Ctx = createContext<IdentityState>({
  identities: [],
  current: null,
  unavailable: false,
  switching: false,
  error: null,
  switchTo: async () => {},
});

const STORAGE_KEY = "review-workbench.identity";

export function IdentityProvider({ children }: { children: React.ReactNode }) {
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [current, setCurrent] = useState<Identity | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetch(`${apiBase.replace(/\/review-api$/, "")}/dev/identities`, {
      credentials: "same-origin",
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(String(r.status));
        return (await r.json()) as { identities?: Identity[] };
      })
      .then((body) => {
        if (!alive) return;
        const list = body.identities ?? [];
        setIdentities(list);
        const saved = window.localStorage.getItem(STORAGE_KEY);
        const pick = list.find((i) => i.id === saved) ?? list[0] ?? null;
        setCurrent(pick);
      })
      .catch(() => {
        // 生产入口没有 /dev/*：如实说「不可用」，不假装已登录
        if (alive) setUnavailable(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (current) window.localStorage.setItem(STORAGE_KEY, current.id);
  }, [current]);

  const switchTo = useCallback(
    async (id: string) => {
      const next = identities.find((i) => i.id === id);
      if (!next) return;
      setSwitching(true);
      setError(null);
      try {
        // 走 dev 入口建 session；vite 需要把 /dev 代理到后端
        const r = await fetch(`${apiBase.replace(/\/review-api$/, "")}/dev/session`, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ principal: id }),
        });
        if (!r.ok) {
          const body = (await r.json().catch(() => null)) as { message?: string } | null;
          throw new Error(body?.message ?? `切换失败：HTTP ${r.status}`);
        }
        setCurrent(next);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setSwitching(false);
      }
    },
    [identities],
  );

  const value = useMemo(
    () => ({ identities, current, unavailable, switching, error, switchTo }),
    [identities, current, unavailable, switching, error, switchTo],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useIdentity(): IdentityState {
  return useContext(Ctx);
}
