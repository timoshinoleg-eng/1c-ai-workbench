import { useQuery } from "@tanstack/react-query";

import * as api from "@/lib/api";
import type { WorkbenchStatus } from "@/types/mcp";

/**
 * Snapshot of the parent workbench: dump path, index stats, server counts.
 */
export function useIndexStatusQuery() {
  return useQuery<WorkbenchStatus>({
    queryKey: ["workbench", "status"],
    queryFn: () => api.getStatus(),
    refetchInterval: 10_000,
  });
}
