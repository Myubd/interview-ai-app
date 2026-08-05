/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** gateway統合ビルド(build:gateway)専用。未設定時は相対パス '/api/v1' を使う。 */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
