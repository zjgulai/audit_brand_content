import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { appOrigin } from "../api/client";
import {
  IdentityContext,
  type Identity,
  type IdentityState,
} from "./IdentitySwitcher";

interface SessionIdentityResponse {
  principal: string;
  tenant: string;
}

const STORAGE_KEY = "review-workbench.dev-identity";

/**
 * 本文件只在 __REVIEW_DEV_IDENTITY__ 为 true 时动态导入。
 * 生产 bundle 不会加载它，也不会读 localStorage 或请求 /dev。
 */
export default function DevIdentityProvider({ children }: { children: React.ReactNode }) {
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [current, setCurrent] = useState<Identity | null>(null);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionEpoch, setSessionEpoch] = useState(0);
  const restoredRef = useRef(false);

  const switchWith = useCallback(async (id: string, known: Identity[]) => {
    const next = known.find((identity) => identity.id === id);
    if (!next) throw new Error("未知开发身份");

    setSwitching(true);
    setError(null);
    setCurrent(null);
    setSessionEpoch((value) => value + 1);
    try {
      const response = await fetch(`${appOrigin}/dev/session`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ principal: id }),
      });
      const payload = (await response.json().catch(() => null)) as
        | SessionIdentityResponse
        | { message?: string }
        | null;
      if (!response.ok) {
        throw new Error(
          payload && "message" in payload && payload.message
            ? payload.message
            : `切换失败：HTTP ${response.status}`,
        );
      }
      if (!payload || !("principal" in payload) || payload.principal !== id) {
        throw new Error("服务端返回的身份与所选身份不一致");
      }
      setCurrent(next);
      window.localStorage.setItem(STORAGE_KEY, next.id);
      setSessionEpoch((value) => value + 1);
      // 保留至少 150ms 的「正在切换开发身份」隔离帧，确保旧案件与备注在 DOM 观察面已清空
      await new Promise((resolve) => window.setTimeout(resolve, 150));
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause));
      throw cause;
    } finally {
      setSwitching(false);
    }
  }, []);

  const enable = useCallback(async () => {
    if (identities.length > 0 || switching) return;
    setSwitching(true);
    setError(null);
    try {
      const response = await fetch(`${appOrigin}/dev/identities`, {
        credentials: "same-origin",
      });
      const payload = (await response.json().catch(() => null)) as
        | { identities?: Identity[]; message?: string }
        | null;
      if (!response.ok) {
        throw new Error(payload?.message ?? `身份列表读取失败：HTTP ${response.status}`);
      }
      const list = payload?.identities ?? [];
      if (list.length === 0) throw new Error("开发身份列表为空");
      setIdentities(list);
      await switchWith(list[0].id, list);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setSwitching(false);
    }
  }, [identities.length, switchWith, switching]);

  const switchTo = useCallback(
    async (id: string) => {
      try {
        await switchWith(id, identities);
      } catch {
        // 错误已写入 context，不留下未捕获 promise。
      }
    },
    [identities, switchWith],
  );

  const value = useMemo<IdentityState>(
    () => ({
      devEnabled: true,
      identities,
      current,
      switching,
      error,
      sessionEpoch,
      enable,
      switchTo,
    }),
    [identities, current, switching, error, sessionEpoch, enable, switchTo],
  );

  useEffect(() => {
    if (restoredRef.current) return;
    restoredRef.current = true;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (!saved) return;
    setSwitching(true);
    setError(null);
    void (async () => {
      try {
        const response = await fetch(`${appOrigin}/dev/identities`, {
          credentials: "same-origin",
        });
        const payload = (await response.json().catch(() => null)) as
          | { identities?: Identity[]; message?: string }
          | null;
        if (!response.ok) throw new Error(payload?.message ?? `HTTP ${response.status}`);
        const list = payload?.identities ?? [];
        setIdentities(list);
        if (!list.some((identity) => identity.id === saved)) {
          window.localStorage.removeItem(STORAGE_KEY);
          throw new Error("已保存的开发身份已失效");
        }
        await switchWith(saved, list); // localStorage 只给候选，成功响应才确认身份。
      } catch (cause: unknown) {
        setCurrent(null);
        setError(cause instanceof Error ? cause.message : String(cause));
      } finally {
        setSwitching(false);
      }
    })();
  }, [switchWith]);

  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>;
}
