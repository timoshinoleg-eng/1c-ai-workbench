import { describe, it, expect, beforeEach, vi } from "vitest";
import { createElement, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react-dom/test-utils";

import { classifyServerError, classifyServerErrorDetails } from "@/lib/mcp/errors";
import { ServerErrorDisplay } from "@/components/mcp/ServerDiagnostics";
import { buildErrorCopyPayload } from "@/lib/api";
import type { McpServerInfo, ServerErrorDetails } from "@/types/mcp";

function renderToContainer(element: ReactElement): { container: HTMLDivElement; root: Root } {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => root.render(element));
  return { container, root };
}

function unmount(root: Root, container: HTMLDivElement) {
  act(() => root.unmount());
  container.remove();
}

function makeServer(details: ServerErrorDetails | null): McpServerInfo {
  return {
    name: "1c-skills",
    description: "test",
    status: "errored",
    version: null,
    command: details?.command ?? "python",
    args: ["tools/skills-bridge/server.py"],
    env: details?.env ?? {},
    enabled: true,
    lastActivity: null,
    lastError: details?.errorClass ?? null,
    lastErrorDetails: details,
  };
}

describe("classifyServerError", () => {
  it("maps binary not found to the workbench-path guidance", () => {
    const result = classifyServerError("binary not found: C:\\missing\\bsl-indexer.exe");
    expect(result.errorClass).toBe("binary_not_found");
    expect(result.userMessage).toContain("Workbench path is wrong");
  });

  it("maps python missing to the python-install guidance", () => {
    const result = classifyServerError("python not in PATH");
    expect(result.errorClass).toBe("python_not_found");
    expect(result.userMessage).toContain("Python 3.10+");
  });

  it("maps server crash / connection closed to the stderr guidance", () => {
    const result = classifyServerError("Connection closed: initialize request");
    expect(result.errorClass).toBe("server_crash");
    expect(result.userMessage).toContain("Server crashed during startup");
  });

  it("maps permission denied to the writable-folder guidance", () => {
    const result = classifyServerError("Permission denied (os error 5)");
    expect(result.errorClass).toBe("permission_denied");
    expect(result.userMessage).toContain("not writable");
  });
});

describe("ServerErrorDisplay", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("shows the actionable binary-not-found message", () => {
    const server = makeServer({
      errorClass: "binary_not_found",
      stderrTail: "",
      command: "C:\\fake\\bsl-indexer.exe",
      env: {},
    });
    const { container, root } = renderToContainer(createElement(ServerErrorDisplay, { server }));
    expect(container.textContent).toContain("Workbench path is wrong");
    unmount(root, container);
  });

  it("shows the actionable python-not-found message", () => {
    const server = makeServer({
      errorClass: "python_not_found",
      stderrTail: "",
      command: "python",
      env: {},
    });
    const { container, root } = renderToContainer(createElement(ServerErrorDisplay, { server }));
    expect(container.textContent).toContain("Python 3.10+");
    unmount(root, container);
  });

  it("shows the actionable server-crash message and stderr tail", () => {
    const server = makeServer({
      errorClass: "server_crash",
      stderrTail: "Traceback: module not found",
      command: "python",
      env: {},
    });
    const { container, root } = renderToContainer(createElement(ServerErrorDisplay, { server }));
    expect(container.textContent).toContain("Server crashed during startup");
    expect(container.textContent).toContain("Traceback");
    unmount(root, container);
  });
});

describe("buildErrorCopyPayload", () => {
  it("redacts sensitive env values before copying", () => {
    const payload = buildErrorCopyPayload({
      errorClass: "server_crash",
      stderrTail: "oops",
      command: "python",
      env: {
        WORKBENCH_ROOT: "C:\\1c-ai-workbench",
        OPENAI_API_KEY: "redacted-test-key",
        SOME_TOKEN: "token-value",
      },
    });
    const parsed = JSON.parse(payload);
    expect(parsed.env.WORKBENCH_ROOT).toBe("C:\\1c-ai-workbench");
    expect(parsed.env.OPENAI_API_KEY).toBe("[REDACTED]");
    expect(parsed.env.SOME_TOKEN).toBe("[REDACTED]");
  });
});

describe("classifyServerErrorDetails", () => {
  it("falls back to stderr tail when errorClass is generic", () => {
    const result = classifyServerErrorDetails({
      errorClass: "something else",
      stderrTail: "binary not found: x.exe",
      command: "x.exe",
      env: {},
    });
    expect(result.errorClass).toBe("binary_not_found");
  });

  it("returns generic when no details are given", () => {
    const result = classifyServerErrorDetails(null);
    expect(result.errorClass).toBe("generic");
  });
});
