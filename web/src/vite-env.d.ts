/// <reference types="vite/client" />

declare const __REVIEW_DEV_IDENTITY__: boolean;
declare const __REVIEW_WRITE_ENABLED__: boolean;

interface ImportMetaEnv {
  readonly VITE_REVIEW_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
