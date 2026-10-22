import { createContext, useContext, useEffect, useState } from "react";
import { reviewApi } from "../api/client";

export interface Identity {
  id: string;
  label: string;
  roles: string[];
  product_lines: string[];
}

export interface IdentityState {
  /** 生产构建恒 false；开发也需显式 opt-in。 */
  devEnabled: boolean;
  identities: Identity[];
  /** 只有开发后端成功建立 session 后才有值。 */
  current: Identity | null;
  switching: boolean;
  error: string | null;
  sessionEpoch: number;
  enable: () => Promise<void>;
  switchTo: (id: string) => Promise<void>;
}

export const EMPTY_IDENTITY: IdentityState = {
  devEnabled: false,
  identities: [],
  current: null,
  switching: false,
  error: null,
  sessionEpoch: 0,
  enable: async () => {},
  switchTo: async () => {},
};

export const IdentityContext = createContext<IdentityState>(EMPTY_IDENTITY);

/**
 * 生产构建只使用这个 Provider；不会读取 localStorage 或请求 /dev。
 * T-150：登录后从 `/api/v1/me` 取当前主体；401 用 `error="unauthorized"` 标记，
 * 由 AppShell 决定跳登录页（本 Provider 不自己导航，避免登录页也被重定向）。
 */
export function ProductionIdentityProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<IdentityState>(EMPTY_IDENTITY);
  useEffect(() => {
    let alive = true;
    reviewApi
      .me()
      .then((me) => {
        if (!alive) return;
        const identity: Identity = {
          id: me.principal,
          label: `${me.principal}（${me.tenant}）`,
          roles: me.roles,
          product_lines: me.product_lines,
        };
        setState({
          ...EMPTY_IDENTITY,
          current: identity,
          identities: [identity],
        });
      })
      .catch((e: unknown) => {
        if (!alive) return;
        const err = e as { status?: number };
        setState({
          ...EMPTY_IDENTITY,
          error: err.status === 401 ? "unauthorized" : "identity_unavailable",
        });
      });
    return () => {
      alive = false;
    };
  }, []);
  return (
    <IdentityContext.Provider value={state}>
      {children}
    </IdentityContext.Provider>
  );
}

export function useIdentity(): IdentityState {
  return useContext(IdentityContext);
}
