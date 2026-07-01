import { useCallback, useState } from "react";
import { Copy, Play, Terminal } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import * as api from "@/lib/api";
import { buildErrorCopyPayload } from "@/lib/api";
import { classifyServerErrorDetails } from "@/lib/mcp/errors";
import type { McpServerInfo, ServerTestResult } from "@/types/mcp";

interface ServerCommandBlockProps {
  server: McpServerInfo;
}

export function ServerCommandBlock({ server }: ServerCommandBlockProps) {
  const { t } = useTranslation();
  const command = [server.command, ...server.args];
  const envEntries = Object.entries(server.env);

  return (
    <div className="space-y-2 text-xs">
      <div>
        <div className="mb-1 font-medium text-muted-foreground">{t("servers.resolvedCommand")}</div>
        <code className="block break-all rounded bg-muted p-2 font-mono">{command.join(" ")}</code>
      </div>
      {envEntries.length > 0 ? (
        <div>
          <div className="mb-1 font-medium text-muted-foreground">{t("servers.resolvedEnv")}</div>
          <div className="rounded bg-muted p-2 font-mono">
            {envEntries.map(([key, value]) => (
              <div key={key} className="break-all">
                <span className="text-primary">{key}</span>=<span>{value}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

interface ServerErrorDisplayProps {
  server: McpServerInfo;
}

export function ServerErrorDisplay({ server }: ServerErrorDisplayProps) {
  const { t } = useTranslation();
  const classified = classifyServerErrorDetails(server.lastErrorDetails);
  const raw = server.lastError ?? classified.userMessage;

  const handleCopy = useCallback(async () => {
    if (!server.lastErrorDetails) {
      await navigator.clipboard.writeText(raw);
      toast.success(t("servers.errorCopied"));
      return;
    }
    const payload = buildErrorCopyPayload(server.lastErrorDetails);
    await navigator.clipboard.writeText(payload);
    toast.success(t("servers.errorCopied"));
  }, [raw, server.lastErrorDetails, t]);

  return (
    <div className="mt-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="text-destructive">{classified.userMessage}</div>
        <Button variant="ghost" size="sm" className="h-7 shrink-0 gap-1 px-2" onClick={handleCopy}>
          <Copy className="h-3.5 w-3.5" />
          {t("servers.copyError")}
        </Button>
      </div>
      {server.lastErrorDetails?.stderrTail ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-muted-foreground">
            {t("servers.showStderr")}
          </summary>
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-background p-2 font-mono text-xs">
            {server.lastErrorDetails.stderrTail}
          </pre>
        </details>
      ) : null}
    </div>
  );
}

interface ServerTestButtonProps {
  server: McpServerInfo;
}

export function ServerTestButton({ server }: ServerTestButtonProps) {
  const { t } = useTranslation();
  const [result, setResult] = useState<ServerTestResult | null>(null);
  const [busy, setBusy] = useState(false);

  const runTest = useCallback(async () => {
    setBusy(true);
    try {
      const testResult = await api.testServer(server.name);
      setResult(testResult);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [server.name]);

  return (
    <div className="space-y-2">
      <Button variant="outline" size="sm" className="gap-1" onClick={runTest} disabled={busy}>
        <Play className="h-3.5 w-3.5" />
        {busy ? t("servers.testing") : t("servers.test")}
      </Button>
      {result ? (
        <div
          className={`rounded-md border p-2 text-xs ${
            result.ok
              ? "border-success/30 bg-success/10 text-success"
              : "border-destructive/30 bg-destructive/10 text-destructive"
          }`}
        >
          <div className="flex items-center gap-1 font-medium">
            <Terminal className="h-3.5 w-3.5" />
            {result.ok
              ? t("servers.testExitOk", { code: result.exitCode ?? "?" })
              : t("servers.testExitFailed", { code: result.exitCode ?? "?" })}
          </div>
          {result.error ? <div className="mt-1 break-all">{result.error}</div> : null}
          {result.stdout ? (
            <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap rounded bg-background/50 p-1.5 font-mono">
              {result.stdout}
            </pre>
          ) : null}
          {result.stderr ? (
            <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap rounded bg-background/50 p-1.5 font-mono">
              {result.stderr}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
