/**
 * MCP request/response types shared between the webview and the Rust core.
 * The Rust side uses serde-derived types in `src-tauri/src/commands.rs`;
 * keep these in sync.
 */
export type ServerStatus = "stopped" | "starting" | "running" | "errored" | "disabled";

export interface ServerErrorDetails {
  errorClass: string;
  stderrTail: string;
  command: string;
  env: Record<string, string>;
}

export interface McpServerInfo {
  name: string;
  description: string;
  status: ServerStatus;
  version: string | null;
  command: string;
  args: string[];
  env: Record<string, string>;
  enabled: boolean;
  lastActivity: string | null;
  lastError: string | null;
  lastErrorDetails: ServerErrorDetails | null;
}

export interface McpToolResult {
  ok: boolean;
  tool: string;
  server: string;
  elapsedMs: number;
  data: unknown;
  error: string | null;
}

export interface WorkbenchStatus {
  dumpPath: string;
  indexExists: boolean;
  indexFileCount: number;
  lastIndexedAt: string | null;
  serversRunning: number;
  serversTotal: number;
  workbenchVersion: string;
}

export interface HealthCheckItem {
  name: string;
  area: string;
  status: "Ready" | "Blocked";
  message: string;
  whyItMatters: string;
  nextStep: string;
}

export interface HealthReport {
  status: "Ready" | "Blocked";
  generatedAt: string;
  passed: number;
  failed: number;
  nextStep: string;
  checks: HealthCheckItem[];
}

export interface ValidationCheck {
  name: string;
  status: "Ready" | "Blocked";
  message: string;
}

export interface ValidationReport {
  ok: boolean;
  path: string;
  xmlFileCount: number;
  metadataDirCount: number;
  checks: ValidationCheck[];
}

export interface ServerTestResult {
  ok: boolean;
  exitCode: number | null;
  stdout: string;
  stderr: string;
  error: string | null;
}

export interface LlmConfig {
  apiKey?: string;
  baseUrl?: string;
  model?: string;
}

export interface CockpitConfig {
  dumpPath: string;
  workbenchPath: string;
  codeIndexHome: string;
  helpDbPath: string;
  servers: Record<
    string,
    {
      enabled: boolean;
      command: string;
      args: string[];
      env: Record<string, string>;
    }
  >;
  llm?: LlmConfig;
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
