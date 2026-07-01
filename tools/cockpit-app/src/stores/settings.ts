/**
 * Persistent settings store. Wraps Zustand with `persist` middleware
 * that targets the Tauri-side config file via IPC (not localStorage,
 * which the webview can wipe on updates).
 */
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

import { loadConfig, saveConfig } from "@/lib/api";
import type { CockpitConfig } from "@/types/mcp";

interface SettingsState {
  config: CockpitConfig | null;
  loaded: boolean;
  loadError: string | null;
  load: () => Promise<void>;
  update: (patch: Partial<CockpitConfig>) => Promise<void>;
  reset: () => Promise<void>;
}

const DEFAULT_CONFIG: CockpitConfig = {
  dumpPath: "C:\\1c-ai-client\\dump",
  workbenchPath: "",
  codeIndexHome: "",
  helpDbPath: "",
  servers: {},
};

function deriveWorkbenchPaths(config: CockpitConfig): CockpitConfig {
  if (!config.workbenchPath) {
    return config;
  }
  return {
    ...config,
    codeIndexHome: config.codeIndexHome || `${config.workbenchPath}\\generated\\code-index-home`,
    helpDbPath: config.helpDbPath || `${config.workbenchPath}\\generated\\help-index\\help-index.db`,
  };
}

export const useSettings = create<SettingsState>()(
  persist(
    (set, get) => ({
      config: null,
      loaded: false,
      loadError: null,
      load: async () => {
        try {
          const config = await loadConfig();
          set({ config, loaded: true, loadError: null });
        } catch (err) {
          // First-run or IPC failure: keep the default in memory so the UI renders.
          set({
            config: get().config ?? DEFAULT_CONFIG,
            loaded: true,
            loadError: err instanceof Error ? err.message : String(err),
          });
        }
      },
      update: async (patch) => {
        const current = get().config ?? DEFAULT_CONFIG;
        const next: CockpitConfig = deriveWorkbenchPaths({ ...current, ...patch });
        set({ config: next });
        await saveConfig(next);
      },
      reset: async () => {
        set({ config: DEFAULT_CONFIG, loaded: true, loadError: null });
        await saveConfig(DEFAULT_CONFIG);
      },
    }),
    {
      name: "cockpit-settings",
      // Fall back to noop storage until the Tauri filesystem is ready;
      // the source of truth is the JSON file in the user's config dir.
      storage: createJSONStorage(() => {
        if (typeof window === "undefined") {
          return {
            getItem: () => null,
            setItem: () => undefined,
            removeItem: () => undefined,
          };
        }
        return window.localStorage;
      }),
      partialize: (state) => ({ config: state.config }),
    },
  ),
);
