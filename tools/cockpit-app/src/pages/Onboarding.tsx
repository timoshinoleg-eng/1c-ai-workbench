import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, FolderOpen, Server, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import {
  ServerCommandBlock,
  ServerErrorDisplay,
  ServerTestButton,
} from "@/components/mcp/ServerDiagnostics";
import * as api from "@/lib/api";
import { mcp } from "@/lib/mcp/client";
import { MCP_SERVER_CATALOG, getServerDisplay } from "@/lib/mcp/servers";
import { useSettings } from "@/stores/settings";
import type { CockpitConfig, McpServerInfo, ValidationReport } from "@/types/mcp";

type StepId = "welcome" | "dump" | "servers" | "index" | "done";

const STEP_IDS: readonly StepId[] = ["welcome", "dump", "servers", "index", "done"] as const;

const STEP_ICONS: Record<StepId, typeof Sparkles> = {
  welcome: Sparkles,
  dump: FolderOpen,
  servers: Server,
  index: Check,
  done: Check,
};

export function Onboarding() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const config = useSettings((state) => state.config);
  const load = useSettings((state) => state.load);
  const update = useSettings((state) => state.update);
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [indexProgress, setIndexProgress] = useState(0);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [configValidation, setConfigValidation] = useState<ValidationReport | null>(null);
  const [servers, setServers] = useState<McpServerInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  const validateFullConfig = useCallback(
    async (candidate = config) => {
      if (!candidate) {
        return null;
      }
      try {
        const report = await api.validateConfig(candidate);
        setConfigValidation(report);
        return report;
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        return null;
      }
    },
    [config],
  );

  const refreshServers = useCallback(async () => {
    setError(null);
    try {
      setServers(await api.listServers());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    if (!config) {
      void load();
    }
  }, [config, load]);

  useEffect(() => {
    void refreshServers();
  }, [refreshServers]);

  useEffect(() => {
    if (config) {
      void validateFullConfig(config);
    }
  }, [config, validateFullConfig]);

  const canMoveNext = useMemo(() => {
    if (step === 1) {
      return validation?.ok === true;
    }
    if (step === 2) {
      return servers.length > 0 && configValidation?.ok === true;
    }
    if (step === 3) {
      return indexProgress === 100;
    }
    return true;
  }, [configValidation?.ok, indexProgress, servers.length, step, validation]);

  function next() {
    setStep((value) => Math.min(value + 1, STEP_IDS.length - 1));
  }

  function back() {
    setStep((value) => Math.max(value - 1, 0));
  }

  async function pickDump() {
    setBusy(true);
    setError(null);
    try {
      const dir = await api.pickDumpDir();
      if (dir) {
        await update({ dumpPath: dir });
        await validateDump(dir);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function pickWorkbench() {
    if (!config) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const dir = await api.pickWorkbenchDir();
      if (dir) {
        const patch: Partial<CockpitConfig> = {
          workbenchPath: dir,
          codeIndexHome: `${dir}\\generated\\code-index-home`,
          helpDbPath: `${dir}\\generated\\help-index\\help-index.db`,
        };
        const nextConfig = { ...config, ...patch };
        await update(patch);
        await validateFullConfig(nextConfig);
        await refreshServers();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function validateDump(path = config?.dumpPath ?? "") {
    if (!path) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const report = await api.validateDumpDir(path);
      setValidation(report);
      if (report.ok) {
        toast.success(t("onboarding.dumpValidated"));
      } else {
        toast.error(t("onboarding.dumpFailed"));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runFirstIndex() {
    setBusy(true);
    setError(null);
    // Do NOT pre-set a fake percentage: indexing can take minutes for a real
    // dump, and a jump from 0 to 15% before the call resolves misleads the
    // operator into thinking it's almost done. Leave the bar at 0 while busy
    // (the button is disabled and the label says "Indexing…"), then move to
    // 100% on success. (sec-fix-2026-06-23, ux-fix)
    try {
      const report = await validateFullConfig();
      if (!report?.ok) {
        throw new Error(t("onboarding.configBlocked"));
      }
      await mcp.start("1c-code-index");
      const response = await mcp.call("1c-code-index", "index", {
        path: config?.dumpPath,
        mode: "incremental",
      });
      if (!response.ok) {
        throw new Error(response.error ?? "index tool failed");
      }
      setIndexProgress(100);
      toast.success(t("onboarding.firstIndexDone"));
    } catch (err) {
      setIndexProgress(0);
      setError(err instanceof Error ? err.message : String(err));
      toast.error(err instanceof Error ? err.message : "Index command failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title={t("onboarding.title")}
        description={t("onboarding.description")}
        actions={
          <Button variant="ghost" size="sm" onClick={() => navigate("/")}>
            {t("onboarding.skip")}
          </Button>
        }
      />
      <div className="scrollbar-thin flex-1 space-y-4 overflow-auto p-6">
        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}
        <div className="grid gap-2 lg:grid-cols-5">
          {STEP_IDS.map((id, index) => {
            const Icon = STEP_ICONS[id];
            const active = index === step;
            const done = index < step;
            return (
              <div
                key={id}
                className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${
                  active
                    ? "border-primary bg-primary/10 text-primary"
                    : done
                      ? "border-success/40 bg-success/10 text-success"
                      : "border-border bg-card/30 text-muted-foreground"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span className="font-medium">{t(`onboarding.step.${id}`)}</span>
              </div>
            );
          })}
        </div>

        {step === 0 ? <WelcomeStep /> : null}
        {step === 1 ? (
          <DumpStep
            path={config?.dumpPath ?? ""}
            validation={validation}
            busy={busy}
            pickDump={pickDump}
            validateDump={() => validateDump()}
          />
        ) : null}
        {step === 2 ? (
          <ServerStep
            servers={servers}
            validation={configValidation}
            busy={busy}
            refreshServers={refreshServers}
            pickWorkbench={pickWorkbench}
            validateConfig={() => validateFullConfig()}
          />
        ) : null}
        {step === 3 ? (
          <IndexStep
            busy={busy}
            progress={indexProgress}
            runFirstIndex={runFirstIndex}
            dumpPath={config?.dumpPath ?? ""}
            configOk={configValidation?.ok === true}
          />
        ) : null}
        {step === 4 ? (
          <Card>
            <CardHeader>
              <CardTitle>{t("onboarding.doneTitle")}</CardTitle>
              <CardDescription>{t("onboarding.doneDescription")}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={() => navigate("/")}>
                <ArrowRight className="mr-2 h-4 w-4" />
                {t("onboarding.openCockpit")}
              </Button>
            </CardContent>
          </Card>
        ) : null}

        <div className="flex justify-between">
          <Button variant="outline" onClick={back} disabled={step === 0}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t("onboarding.back")}
          </Button>
          <Button onClick={next} disabled={step === STEP_IDS.length - 1 || !canMoveNext}>
            {t("onboarding.next")}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function WelcomeStep() {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("onboarding.welcomeTitle")}</CardTitle>
        <CardDescription>{t("onboarding.welcomeDescription")}</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="ml-5 list-disc space-y-1 text-sm text-muted-foreground">
          <li>{t("onboarding.welcomeBullets.servers")}</li>
          <li>{t("onboarding.welcomeBullets.search")}</li>
          <li>{t("onboarding.welcomeBullets.validate")}</li>
        </ul>
      </CardContent>
    </Card>
  );
}

function DumpStep({
  path,
  validation,
  busy,
  pickDump,
  validateDump,
}: {
  path: string;
  validation: ValidationReport | null;
  busy: boolean;
  pickDump: () => Promise<void>;
  validateDump: () => Promise<void>;
}) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("onboarding.dumpTitle")}</CardTitle>
        <CardDescription>{t("onboarding.dumpDescription")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Input value={path} readOnly />
          <Button onClick={pickDump} variant="outline" disabled={busy}>
            <FolderOpen className="mr-2 h-4 w-4" />
            {t("onboarding.pick")}
          </Button>
          <Button onClick={validateDump} disabled={busy || !path}>
            {t("onboarding.validate")}
          </Button>
        </div>
        {validation ? <ValidationTable validation={validation} /> : null}
      </CardContent>
    </Card>
  );
}

function ServerStep({
  servers,
  validation,
  busy,
  refreshServers,
  pickWorkbench,
  validateConfig,
}: {
  servers: McpServerInfo[];
  validation: ValidationReport | null;
  busy: boolean;
  refreshServers: () => Promise<void>;
  pickWorkbench: () => Promise<void>;
  validateConfig: () => Promise<ValidationReport | null>;
}) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("onboarding.serversTitle")}</CardTitle>
        <CardDescription>{t("onboarding.serversDescription")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => void refreshServers()}>
            {t("onboarding.refresh")}
          </Button>
          <Button variant="outline" size="sm" onClick={pickWorkbench} disabled={busy}>
            <FolderOpen className="mr-2 h-4 w-4" />
            {t("onboarding.pickWorkbench")}
          </Button>
          <Button size="sm" onClick={() => void validateConfig()} disabled={busy}>
            {t("onboarding.validateConfig")}
          </Button>
        </div>
        {validation ? <ValidationTable validation={validation} /> : null}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("onboarding.serverTable.server")}</TableHead>
              <TableHead>{t("onboarding.serverTable.status")}</TableHead>
              <TableHead>{t("onboarding.serverTable.command")}</TableHead>
              <TableHead>{t("onboarding.serverTable.diagnostics")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {MCP_SERVER_CATALOG.map((entry) => {
              const live = servers.find((server) => server.name === entry.id);
              const { name } = getServerDisplay(entry, t);
              return (
                <TableRow key={entry.id}>
                  <TableCell>{name}</TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        live?.status === "running"
                          ? "success"
                          : live?.status === "errored"
                            ? "destructive"
                            : "secondary"
                      }
                    >
                      {live?.status ?? (entry.defaultEnabled ? "stopped" : "disabled")}
                    </Badge>
                  </TableCell>
                  <TableCell className="max-w-[520px]">
                    {live ? <ServerCommandBlock server={live} /> : t("onboarding.notLoaded")}
                  </TableCell>
                  <TableCell className="max-w-[360px]">
                    {live ? (
                      <div className="space-y-2">
                        <ServerTestButton server={live} />
                        {live.status === "errored" || live.lastErrorDetails ? (
                          <ServerErrorDisplay server={live} />
                        ) : null}
                      </div>
                    ) : null}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function ValidationTable({ validation }: { validation: ValidationReport }) {
  const { t } = useTranslation();
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("onboarding.check.name")}</TableHead>
          <TableHead>{t("onboarding.check.status")}</TableHead>
          <TableHead>{t("onboarding.check.message")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {validation.checks.map((check) => (
          <TableRow key={check.name}>
            <TableCell>{check.name}</TableCell>
            <TableCell>
              <Badge variant={check.status === "Ready" ? "success" : "destructive"}>{check.status}</Badge>
            </TableCell>
            <TableCell className="break-all">{check.message}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function IndexStep({
  busy,
  progress,
  runFirstIndex,
  dumpPath,
  configOk,
}: {
  busy: boolean;
  progress: number;
  runFirstIndex: () => Promise<void>;
  dumpPath: string;
  configOk: boolean;
}) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("onboarding.indexTitle")}</CardTitle>
        <CardDescription>
          {t("onboarding.indexDescription", { path: dumpPath || "selected dump" })}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Progress value={progress} />
        {!configOk ? <div className="text-sm text-destructive">{t("onboarding.configBlocked")}</div> : null}
        <Button onClick={runFirstIndex} disabled={busy || !configOk}>
          {busy
            ? t("onboarding.indexButtonBusy")
            : progress === 100
              ? t("onboarding.indexButtonDone")
              : t("onboarding.indexButtonIdle")}
        </Button>
        {progress === 100 ? (
          <span className="text-xs text-success">{t("onboarding.indexCompleted")}</span>
        ) : null}
      </CardContent>
    </Card>
  );
}
