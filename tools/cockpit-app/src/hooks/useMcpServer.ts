import { useQuery } from "@tanstack/react-query";

import { mcp } from "@/lib/mcp/client";
import type { McpServerInfo } from "@/types/mcp";

/**
 * Polls `list_servers` on a 5s interval so the Cockpit reflects state
 * changes (e.g., a child process that crashed) without manual refresh.
 */
export function useMcpServers() {
  return useQuery<McpServerInfo[]>({
    queryKey: ["mcp", "servers"],
    queryFn: () => mcp.list(),
    refetchInterval: 5_000,
  });
}
