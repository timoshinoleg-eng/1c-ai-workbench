/**
 * Static catalog of MCP servers that the Cockpit can launch.
 * The Rust side has the source of truth in `src-tauri/src/commands.rs`;
 * this file mirrors it for the UI so pages can render even before the
 * first IPC roundtrip resolves.
 */
import type { TFunction } from "i18next";

import type { ServerStatus } from "@/types/mcp";

export interface McpServerCatalogEntry {
  id: string;
  displayName: string;
  shortDescription: string;
  icon: string;
  defaultEnabled: boolean;
  /**
   * Optional Phase B / experimental flag. Disabled by default in production
   * per the parent workbench policy.
   */
  experimental?: boolean;
}

export const MCP_SERVER_CATALOG: McpServerCatalogEntry[] = [
  {
    id: "1c-code-index",
    displayName: "1C Code Index",
    shortDescription: "BSL code navigation, object metadata, call graph",
    icon: "Code2",
    defaultEnabled: true,
  },
  {
    id: "1c-skills",
    displayName: "1C Skills",
    shortDescription: "Read-only 1C-specific skills (16 tools)",
    icon: "Wrench",
    defaultEnabled: true,
  },
  {
    id: "1c-prompt-gallery",
    displayName: "1C Prompt Gallery",
    shortDescription: "Prompt catalog exposed as callable tools",
    icon: "Library",
    defaultEnabled: true,
  },
  {
    id: "1c-help-index",
    displayName: "1C Help Index",
    shortDescription: "Local 1C .hbk help search",
    icon: "BookOpen",
    defaultEnabled: true,
  },
  {
    id: "1c-ibcmd",
    displayName: "1C ibcmd",
    shortDescription: "Phase B export/import (experimental, disabled by default)",
    icon: "Database",
    defaultEnabled: false,
    experimental: true,
  },
];

/**
 * Resolve the localized display name + description for a catalog entry.
 * Falls back to the static English fields baked into the catalog when the
 * active language has no translation (or when running outside a TFunction
 * context such as the Rust mock IPC path).
 */
export function getServerDisplay(
  entry: McpServerCatalogEntry,
  t: TFunction,
): { name: string; description: string } {
  const name = t(`servers.${entry.id}.name`, { defaultValue: entry.displayName });
  const description = t(`servers.${entry.id}.description`, {
    defaultValue: entry.shortDescription,
  });
  return { name, description };
}

/**
 * Localize a server runtime status. `experimental` and `disabled` are
 * shared with the catalog metadata flag.
 */
export function getServerStatusLabel(status: ServerStatus, t: TFunction): string {
  return t(`cockpit.status.${status}`, { defaultValue: status });
}

export function statusColor(status: ServerStatus): "green" | "yellow" | "red" | "gray" {
  switch (status) {
    case "running":
      return "green";
    case "starting":
      return "yellow";
    case "errored":
      return "red";
    case "stopped":
      return "gray";
    case "disabled":
      return "gray";
  }
}
