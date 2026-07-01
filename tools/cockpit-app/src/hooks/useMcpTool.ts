import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { mcp } from "@/lib/mcp/client";
import type { McpToolResult } from "@/types/mcp";

/**
 * Call a tool on a specific MCP server. Mutations invalidate the
 * `["mcp", "servers"]` cache so the status row reflects the call.
 */
export function useMcpTool<TArgs extends Record<string, unknown> = Record<string, unknown>>(
  server: string,
  tool: string,
) {
  const qc = useQueryClient();
  const query = useQuery<McpToolResult>({
    queryKey: ["mcp", "tool", server, tool],
    queryFn: () => mcp.call(server, tool, {} as TArgs),
    enabled: false,
  });
  const mutation = useMutation({
    mutationFn: (args: TArgs) => mcp.call(server, tool, args),
    onSettled: () => qc.invalidateQueries({ queryKey: ["mcp", "servers"] }),
  });
  return { ...query, invoke: mutation.mutate, invokeAsync: mutation.mutateAsync, invoking: mutation.isPending };
}
