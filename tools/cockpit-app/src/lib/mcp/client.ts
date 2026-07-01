/**
 * Thin wrapper around the Rust-side MCP client.
 * The Rust process owns the actual stdio transport; this client only
 * relays typed JSON over Tauri's IPC bridge.
 */
import * as api from "@/lib/api";
import type { McpServerInfo, McpToolResult } from "@/types/mcp";

export class McpClient {
  async list(): Promise<McpServerInfo[]> {
    return api.listServers();
  }

  async start(name: string): Promise<void> {
    return api.startServer(name);
  }

  async stop(name: string): Promise<void> {
    return api.stopServer(name);
  }

  async restart(name: string): Promise<void> {
    return api.restartServer(name);
  }

  async call(server: string, tool: string, args: Record<string, unknown> = {}): Promise<McpToolResult> {
    return api.callTool(server, tool, args);
  }

  async ping(name: string): Promise<{ ok: boolean; latencyMs: number }> {
    return api.pingServer(name);
  }
}

export const mcp = new McpClient();
