// frontend/src/vite-env.d.ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  // 以后如果有其他 VITE_ 开头的环境变量，也在这里声明
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}