/**
 * Type-safe wrappers around Tauri `invoke` calls.
 * Every Tauri command exposed in `src-tauri/src/commands.rs` should have a
 * matching wrapper here. Never call `invoke()` from page code directly.
 */
import { invoke } from "@tauri-apps/api/core";

import { MCP_SERVER_CATALOG } from "@/lib/mcp/servers";
import type {
  CockpitConfig,
  HealthReport,
  McpServerInfo,
  McpToolResult,
  ServerErrorDetails,
  ServerTestResult,
  ValidationReport,
  WorkbenchStatus,
} from "@/types/mcp";

const DEFAULT_CONFIG: CockpitConfig = {
  dumpPath: "C:\\1c-ai-client\\dump",
  workbenchPath: "",
  codeIndexHome: "",
  helpDbPath: "",
  servers: {},
};

const mockServers: McpServerInfo[] = MCP_SERVER_CATALOG.map((entry) => ({
  name: entry.id,
  description: entry.shortDescription,
  status: entry.defaultEnabled ? "stopped" : "disabled",
  version: null,
  command: entry.id === "1c-code-index" ? "bsl-indexer.exe" : "python",
  args: [],
  env: {},
  enabled: entry.defaultEnabled,
  lastActivity: null,
  lastError: null,
  lastErrorDetails: null,
}));

let mockConfig = DEFAULT_CONFIG;

function shouldUseMockInvoke(): boolean {
  if (import.meta.env.MODE !== "test" || typeof window === "undefined") {
    return false;
  }
  return !("__TAURI_INTERNALS__" in (window as Window & { __TAURI_INTERNALS__?: unknown }));
}

async function invokeCommand<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  if (!shouldUseMockInvoke()) {
    return invoke<T>(command, args);
  }
  return mockInvoke<T>(command, args ?? {});
}

async function mockInvoke<T>(command: string, args: Record<string, unknown>): Promise<T> {
  switch (command) {
    case "list_servers":
      return structuredClone(mockServers) as T;
    case "start_server": {
      const name = String(args.name);
      const server = mockServers.find((item) => item.name === name);
      if (server && server.enabled) {
        server.status = "running";
        server.lastActivity = new Date().toISOString();
      }
      return undefined as T;
    }
    case "stop_server": {
      const name = String(args.name);
      const server = mockServers.find((item) => item.name === name);
      if (server && server.enabled) {
        server.status = "stopped";
      }
      return undefined as T;
    }
    case "restart_server":
      await mockInvoke("stop_server", args);
      await mockInvoke("start_server", args);
      return undefined as T;
    case "test_server": {
      const name = String(args.name);
      const server = mockServers.find((item) => item.name === name);
      if (!server) {
        return { ok: false, exitCode: null, stdout: "", stderr: "", error: `unknown server '${name}'` } as ServerTestResult as T;
      }
      if (server.command === "missing-binary.exe") {
        return { ok: false, exitCode: null, stdout: "", stderr: "", error: "binary not found: missing-binary.exe" } as ServerTestResult as T;
      }
      if (server.command === "python-missing") {
        return { ok: false, exitCode: null, stdout: "", stderr: "", error: "python not in PATH" } as ServerTestResult as T;
      }
      return { ok: true, exitCode: 0, stdout: "mock stdout", stderr: "", error: null } as ServerTestResult as T;
    }
    case "call_tool":
      return mockToolResult(
        String(args.server),
        String(args.tool),
        (args.args ?? {}) as Record<string, unknown>,
      ) as T;
    case "get_status":
      return {
        dumpPath: mockConfig.dumpPath,
        indexExists: true,
        indexFileCount: 42,
        lastIndexedAt: new Date().toISOString(),
        serversRunning: mockServers.filter((server) => server.status === "running").length,
        serversTotal: mockServers.length,
        workbenchVersion: "0.2.0-test",
      } as WorkbenchStatus as T;
    case "load_config":
      return structuredClone(mockConfig) as T;
    case "save_config":
      mockConfig = structuredClone(args.config as CockpitConfig);
      return undefined as T;
    case "validate_dump_dir":
      return {
        ok: true,
        path: String(args.path),
        xmlFileCount: 12,
        metadataDirCount: 4,
        checks: [
          { name: "path exists", status: "Ready", message: String(args.path) },
          { name: "XML files", status: "Ready", message: "12 XML files found" },
        ],
      } as ValidationReport as T;
    case "validate_config":
      return {
        ok: true,
        path: String((args.config as CockpitConfig | undefined)?.workbenchPath ?? ""),
        xmlFileCount: 12,
        metadataDirCount: 4,
        checks: [
          { name: "dump directory", status: "Ready", message: "C:\\1c-ai-client\\dump" },
          { name: "dump layout", status: "Ready", message: "Configuration.xml found" },
          { name: "workbench directory", status: "Ready", message: "mock workbench" },
          { name: "bsl-indexer binary", status: "Ready", message: "mock bsl-indexer.exe" },
        ],
      } as ValidationReport as T;
    case "pick_dump_dir":
      return "C:\\1c-ai-client\\dump" as T;
    case "pick_workbench_dir":
      return "C:\\1c-ai-workbench" as T;
    case "run_healthcheck":
      return {
        status: "Ready",
        generatedAt: new Date().toISOString(),
        passed: 4,
        failed: 0,
        nextStep: "Start the MCP servers.",
        checks: [],
      } as HealthReport as T;
    case "ping_server":
      return { ok: true, latencyMs: 4 } as T;
    case "open_config_file":
      return undefined as T;
    default:
      throw new Error(`Unhandled mock Tauri command: ${command}`);
  }
}

function mockToolResult(server: string, tool: string, args: Record<string, unknown>): McpToolResult {
  let data: unknown = { ok: true };
  if (tool === "search_text" || tool === "grep_body") {
    data = {
      matches: [
        {
          file: "Catalogs/Products/Ext/ObjectModule.bsl",
          path: "Catalogs/Products/Ext/ObjectModule.bsl",
          line: 12,
          line_start: 12,
          line_end: 14,
          snippet: `Mock result for ${String(args.query ?? args.pattern ?? "")}`,
        },
      ],
    };
  } else if (tool === "get_help_tree") {
    data = { ok: true, data: { children: [{ id: 1, title: "Objects", name: "Objects" }] } };
  } else if (tool === "smart_search_help") {
    data = { ok: true, data: { results: [{ id: 1, title: "Query language", snippet: "SELECT examples" }] } };
  } else if (tool === "get_help_topic") {
    data = { ok: true, data: { id: args.topic_id, title: "Topic", content: "<p>Mock help topic</p>" } };
  } else if (tool === "risk_scan") {
    data = {
      findings: [
        {
          severity: "medium",
          category: "query",
          title: "SELECT * detected",
          object: "Catalogs.Products",
          confidence: 0.8,
          path: "Catalogs/Products.xml",
        },
      ],
    };
  }
  return { ok: true, tool, server, elapsedMs: 3, data, error: null };
}

export async function listServers(): Promise<McpServerInfo[]> {
  return invokeCommand<McpServerInfo[]>("list_servers");
}

export async function startServer(name: string): Promise<void> {
  await invokeCommand("start_server", { name });
}

export async function stopServer(name: string): Promise<void> {
  await invokeCommand("stop_server", { name });
}

export async function restartServer(name: string): Promise<void> {
  await invokeCommand("restart_server", { name });
}

export async function callTool(
  server: string,
  tool: string,
  args: Record<string, unknown>,
): Promise<McpToolResult> {
  return invokeCommand<McpToolResult>("call_tool", { server, tool, args });
}

export async function getStatus(): Promise<WorkbenchStatus> {
  return invokeCommand<WorkbenchStatus>("get_status");
}

export async function loadConfig(): Promise<CockpitConfig> {
  return invokeCommand<CockpitConfig>("load_config");
}

export async function saveConfig(config: CockpitConfig): Promise<void> {
  await invokeCommand("save_config", { config });
}

export async function validateDumpDir(path: string): Promise<ValidationReport> {
  return invokeCommand<ValidationReport>("validate_dump_dir", { path });
}

export async function validateConfig(config: CockpitConfig): Promise<ValidationReport> {
  return invokeCommand<ValidationReport>("validate_config", { config });
}

export async function pickDumpDir(): Promise<string | null> {
  return invokeCommand<string | null>("pick_dump_dir");
}

export async function pickWorkbenchDir(): Promise<string | null> {
  return invokeCommand<string | null>("pick_workbench_dir");
}

export async function runHealthcheck(): Promise<HealthReport> {
  return invokeCommand<HealthReport>("run_healthcheck");
}

export async function pingServer(name: string): Promise<{ ok: boolean; latencyMs: number }> {
  return invokeCommand<{ ok: boolean; latencyMs: number }>("ping_server", { name });
}

export async function testServer(name: string): Promise<ServerTestResult> {
  return invokeCommand<ServerTestResult>("test_server", { name });
}

export async function openConfigFile(): Promise<void> {
  await invokeCommand("open_config_file");
}

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  toolCallId?: string;
  name?: string;
  toolCalls?: unknown;
}

export interface ChatTurn {
  role: string;
  content: string;
  toolName?: string;
  toolResult?: string;
}

export interface ChatResponse {
  finalText: string;
  turns: ChatTurn[];
  model: string;
}

export async function chatSend(messages: ChatMessage[]): Promise<ChatResponse> {
  return invokeCommand<ChatResponse>("chat_send", { messages });
}

export function buildErrorCopyPayload(details: ServerErrorDetails): string {
  return JSON.stringify(
    {
      error_class: details.errorClass,
      stderr_tail: details.stderrTail,
      command: details.command,
      env: redactEnv(details.env),
    },
    null,
    2,
  );
}

function redactEnv(env: Record<string, string>): Record<string, string> {
  const sensitive = /token|key|secret|password|credential|api/i;
  return Object.fromEntries(
    Object.entries(env).map(([k, v]) => [k, sensitive.test(k) ? "[REDACTED]" : v]),
  );
}
