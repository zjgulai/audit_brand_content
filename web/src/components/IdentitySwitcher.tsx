import { createContext, useContext } from "react";

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

/** 生产构建只使用这个 Provider；不会读取 localStorage 或请求 /dev。 */
export function ProductionIdentityProvider({ children }: { children: React.ReactNode }) {
  return (
    <IdentityContext.Provider value={EMPTY_IDENTITY}>
      {children}
    </IdentityContext.Provider>
  );
}

export function useIdentity(): IdentityState {
  return useContext(IdentityContext);
}
