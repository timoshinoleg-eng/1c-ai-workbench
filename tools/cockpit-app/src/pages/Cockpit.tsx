import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Play, Square, RefreshCw, Stethoscope, Server,
  Code2, Wrench, Library, BookOpen, Database,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { MCP_SERVER_CATALOG, statusColor, getServerDisplay, getServerStatusLabel } from "@/lib/mcp/servers";
import * as api from "@/lib/api";
import { mcp } from "@/lib/mcp/client";
import { useMcpServers } from "@/hooks/useMcpServer";
import { useIndexStatusQuery } from "@/hooks/useIndexStatus";
import { cn, formatTimestamp } from "@/lib/utils";

const ICON_MAP: Record<string, LucideIcon> = {
  Code2,
  Wrench,
  Library,
  BookOpen,
  Database,
  Server,
};

export function Cockpit() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language.startsWith("ru") ? "ru-RU" : "en-US";
  const qc = useQueryClient();
  const serversQ = useMcpServers();
  const statusQ = useIndexStatusQuery();
  const healthcheckQ = useQuery({
    queryKey: ["workbench", "healthcheck"],
    queryFn: () => api.runHealthcheck(),
    enabled: false,
  });
  const [busy, setBusy] = useState(false);

  async function startAll() {
    setBusy(true);
    try {
      const running = (serversQ.data ?? []).filter((s) => s.status === "running").map((s) => s.name);
      const toStart = (serversQ.data ?? [])
        .filter((s) => s.enabled && !running.includes(s.name))
        .map((s) => s.name);
      await Promise.all(toStart.map((n) => mcp.start(n).catch(() => undefined)));
      await qc.invalidateQueries({ queryKey: ["mcp", "servers"] });
      await qc.invalidateQueries({ queryKey: ["workbench", "status"] });
      toast.success(`Started ${toStart.length} server(s)`);
    } finally {
      setBusy(false);
    }
  }

  async function stopAll() {
    setBusy(true);
    try {
      const running = (serversQ.data ?? []).filter((s) => s.status === "running").map((s) => s.name);
      await Promise.all(running.map((n) => mcp.stop(n).catch(() => undefined)));
      await qc.invalidateQueries({ queryKey: ["mcp", "servers"] });
      await qc.invalidateQueries({ queryKey: ["workbench", "status"] });
      toast.success(`Stopped ${running.length} server(s)`);
    } finally {
      setBusy(false);
    }
  }

  async function runHealth() {
    setBusy(true);
    try {
      const report = await healthcheckQ.refetch();
      if (report.data?.status === "Ready") {
        toast.success(`Health check: ${report.data.passed} passed`);
      } else {
        toast.error(`Health check failed: ${report.data?.failed ?? 0} issue(s)`);
      }
    } finally {
      setBusy(false);
    }
  }

  const servers = serversQ.data ?? [];
  const serverError = serversQ.error instanceof Error ? serversQ.error.message : null;
  const statusError = statusQ.error instanceof Error ? statusQ.error.message : null;
  const runningCount = servers.filter((s) => s.status === "running").length;

  async function runServerAction(action: "start" | "stop" | "restart", name: string) {
    setBusy(true);
    try {
      if (action === "start") {
        await mcp.start(name);
      } else if (action === "stop") {
        await mcp.stop(name);
      } else {
        await mcp.restart(name);
      }
      await qc.invalidateQueries({ queryKey: ["mcp", "servers"] });
      await qc.invalidateQueries({ queryKey: ["workbench", "status"] });
      toast.success(`${name}: ${action} complete`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `${name}: ${action} failed`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title={t("cockpit.title")}
        description={
          statusQ.data
            ? `${t("cockpit.serversRunning", { running: runningCount, total: servers.length })} · ${t("cockpit.filesIndexed", { files: statusQ.data.indexFileCount.toLocaleString(locale) })}`
            : t("common.loading")
        }
        actions={
          <div className="flex items-center gap-2">
            <Button variant="default" size="sm" className="h-9" onClick={startAll} disabled={busy}>
              <Play className="mr-2 h-4 w-4" /> {t("cockpit.startAll")}
            </Button>
            <Button variant="default" size="sm" className="h-9" onClick={stopAll} disabled={busy}>
              <Square className="mr-2 h-4 w-4" /> {t("cockpit.stopAll")}
            </Button>
            <Button variant="outline" size="sm" className="h-9" onClick={runHealth} disabled={busy}>
              <Stethoscope className="mr-2 h-4 w-4" /> {t("cockpit.healthCheck")}
            </Button>
          </div>
        }
      />

      <div className="flex-1 space-y-6 overflow-auto scrollbar-thin p-6">
        {serverError || statusError ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {serverError ?? statusError}
          </div>
        ) : null}
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            {t("cockpit.mcpServers")}
          </h2>
          <TooltipProvider delayDuration={150}>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {MCP_SERVER_CATALOG.map((entry) => {
                const live = servers.find((s) => s.name === entry.id);
                const status = live?.status ?? (entry.defaultEnabled ? "stopped" : "disabled");
                const color = statusColor(status);
                const { name, description } = getServerDisplay(entry, t);
                const statusLabel = getServerStatusLabel(status, t);
                const ServerIcon = ICON_MAP[entry.icon] ?? Server;
                const iconClass =
                  status === "running"
                    ? "text-emerald-400"
                    : status === "starting"
                      ? "text-yellow-400"
                      : status === "errored"
                        ? "text-red-400"
                        : "text-muted-foreground";
                const dotClass =
                  status === "running"
                    ? "bg-emerald-400 animate-pulse-slow"
                    : status === "starting"
                      ? "bg-yellow-400 animate-pulse-fast"
                      : status === "errored"
                        ? "bg-red-500"
                        : status === "disabled"
                          ? "bg-zinc-600"
                          : "bg-zinc-500";
                return (
                  <Card
                    key={entry.id}
                    data-testid={`server-card-${entry.id}`}
                    className="transition-all duration-200 hover:border-zinc-700 hover:shadow-lg hover:shadow-black/20 hover:-translate-y-0.5"
                  >
                    <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
                      <div className="flex items-start gap-3">
                        <div className={cn(
                          "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted/50 transition-colors",
                          status === "running" && "bg-emerald-500/10",
                        )}>
                          <ServerIcon className={cn("h-5 w-5 transition-colors", iconClass)} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <CardTitle className="text-base leading-tight">{name}</CardTitle>
                          <CardDescription className="mt-1 text-xs leading-relaxed">
                            {description}
                          </CardDescription>
                        </div>
                      </div>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span
                            className={cn(
                              "relative inline-flex h-3.5 w-3.5 shrink-0 cursor-help rounded-full ring-2 ring-background",
                              dotClass,
                            )}
                            data-status={color}
                            aria-label={statusLabel}
                          >
                            {status === "running" ? (
                              <span className="absolute inset-0 rounded-full bg-emerald-400/70 animate-ping" />
                            ) : status === "starting" ? (
                              <span className="absolute inset-0 rounded-full bg-yellow-400/60 animate-ping" />
                            ) : null}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>{statusLabel}</TooltipContent>
                      </Tooltip>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <Badge variant={status === "running" ? "success" : status === "errored" ? "destructive" : "secondary"}>
                          {statusLabel}
                        </Badge>
                        {live?.version ? <span>v{live.version}</span> : null}
                        {entry.experimental ? <Badge variant="warning">{t("cockpit.status.experimental")}</Badge> : null}
                      </div>
                      <Separator />
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>
                          {t("cockpit.lastActivity")} {formatTimestamp(live?.lastActivity ?? null, locale)}
                        </span>
                        <div className="flex items-center gap-1">
                          {status === "running" ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              aria-label={`${t("cockpit.actions.stop")} ${name}`}
                              disabled={busy}
                              onClick={() => runServerAction("stop", entry.id)}
                            >
                              <Square className="h-3.5 w-3.5" />
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="sm"
                              aria-label={`${t("cockpit.actions.start")} ${name}`}
                              disabled={status === "disabled" || busy}
                              onClick={() => runServerAction("start", entry.id)}
                            >
                              <Play className="h-3.5 w-3.5" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`${t("cockpit.actions.restart")} ${name}`}
                            disabled={status === "disabled" || busy}
                            onClick={() => runServerAction("restart", entry.id)}
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                      {live?.lastError ? (
                        <p className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
                          {live.lastError}
                        </p>
                      ) : null}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </TooltipProvider>
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            {t("cockpit.recentQueries")}
          </h2>
          <EmptyState
            title={t("cockpit.noQueries")}
            description={t("cockpit.noQueriesHint")}
          />
        </section>
      </div>
    </div>
  );
}
