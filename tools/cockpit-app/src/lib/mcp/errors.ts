import type { ServerErrorDetails } from "@/types/mcp";

export type ErrorClass =
  | "binary_not_found"
  | "python_not_found"
  | "server_script_not_found"
  | "spawn_failed"
  | "server_crash"
  | "permission_denied"
  | "timeout"
  | "stdio_error"
  | "not_running"
  | "generic";

export interface ClassifiedError {
  errorClass: ErrorClass;
  userMessage: string;
}

const USER_ACTIONABLE_MESSAGES: Record<ErrorClass, string> = {
  binary_not_found:
    "Workbench path is wrong. Open Settings → Путь к Workbench and verify the folder contains tools\\, scripts\\, opencode.jsonc.",
  python_not_found:
    "Python 3.10+ is required. Install from python.org and ensure it's on PATH. Restart Cockpit after install.",
  server_script_not_found:
    "Workbench layout is incomplete. Reinstall or browse to a valid 1c-ai-workbench root.",
  spawn_failed: "Server crashed during startup. Check the logs panel for the stderr output.",
  server_crash: "Server crashed during startup. Check the logs panel for the stderr output.",
  permission_denied:
    "The workbench folder is not writable. Move it out of C:\\Program Files\\ or run as a user that owns the folder.",
  timeout: "Server did not respond in time. Check the logs panel for the stderr output.",
  stdio_error: "Server crashed during startup. Check the logs panel for the stderr output.",
  not_running:
    "Server is not running. Check Settings → Workbench path and start the server.",
  generic: "Server failed to start. Check the logs panel for the stderr output.",
};

export function classifyServerError(message: string): ClassifiedError {
  const lower = message.toLowerCase();
  let errorClass: ErrorClass = "generic";

  if (lower.includes("binary not found")) {
    errorClass = "binary_not_found";
  } else if (
    (lower.includes("not in path") || lower.includes("command not found") || lower.includes("not found in path")) &&
    lower.includes("python")
  ) {
    errorClass = "python_not_found";
  } else if (lower.includes("server script not found")) {
    errorClass = "server_script_not_found";
  } else if (lower.includes("permission denied")) {
    errorClass = "permission_denied";
  } else if (lower.includes("timed out") || lower.includes("timeout")) {
    errorClass = "timeout";
  } else if (
    lower.includes("process exited") ||
    lower.includes("stdout closed") ||
    lower.includes("connection closed")
  ) {
    errorClass = "server_crash";
  } else if (lower.includes("spawn failed")) {
    errorClass = "spawn_failed";
  } else if (lower.includes("not running")) {
    errorClass = "not_running";
  }

  return {
    errorClass,
    userMessage: USER_ACTIONABLE_MESSAGES[errorClass],
  };
}

function classifyByClassName(errorClass: string): ClassifiedError | null {
  const normalized = errorClass.toLowerCase().replace(/[-_]/g, "_");
  const known: ErrorClass[] = [
    "binary_not_found",
    "python_not_found",
    "server_script_not_found",
    "spawn_failed",
    "server_crash",
    "permission_denied",
    "timeout",
    "stdio_error",
    "not_running",
  ];
  const match = known.find((k) => normalized === k || normalized.includes(k));
  if (match) {
    return { errorClass: match, userMessage: USER_ACTIONABLE_MESSAGES[match] };
  }
  return null;
}

export function classifyServerErrorDetails(
  details: ServerErrorDetails | null,
): ClassifiedError {
  if (!details) {
    return { errorClass: "generic", userMessage: USER_ACTIONABLE_MESSAGES.generic };
  }
  const fromClass = classifyByClassName(details.errorClass);
  if (fromClass) {
    return fromClass;
  }
  const fromMessage = classifyServerError(details.errorClass);
  if (fromMessage.errorClass !== "generic") {
    return fromMessage;
  }
  return classifyServerError(details.stderrTail || details.errorClass);
}
