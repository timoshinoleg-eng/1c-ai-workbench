import { describe, it, expect } from "vitest";
import { MCP_SERVER_CATALOG, statusColor } from "@/lib/mcp/servers";

describe("MCP_SERVER_CATALOG", () => {
  it("contains exactly the 5 documented servers", () => {
    const ids = MCP_SERVER_CATALOG.map((s) => s.id);
    expect(ids).toEqual([
      "1c-code-index",
      "1c-skills",
      "1c-prompt-gallery",
      "1c-help-index",
      "1c-ibcmd",
    ]);
  });

  it("marks the experimental Phase B server as disabled by default", () => {
    const ibcmd = MCP_SERVER_CATALOG.find((s) => s.id === "1c-ibcmd");
    expect(ibcmd?.defaultEnabled).toBe(false);
    expect(ibcmd?.experimental).toBe(true);
  });
});

describe("statusColor", () => {
  it("maps statuses to traffic-light colors", () => {
    expect(statusColor("running")).toBe("green");
    expect(statusColor("starting")).toBe("yellow");
    expect(statusColor("errored")).toBe("red");
    expect(statusColor("stopped")).toBe("gray");
    expect(statusColor("disabled")).toBe("gray");
  });
});
