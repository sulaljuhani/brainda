/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_API_BASE_PATH: string;
  readonly VITE_APP_NAME: string;
  readonly VITE_APP_VERSION: string;
  readonly VITE_ENABLE_GOOGLE_CALENDAR: string;
  readonly VITE_ENABLE_OPENMEMORY: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
