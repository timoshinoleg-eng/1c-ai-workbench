import { useEffect, useState } from "react";
import { Eye, EyeOff, FolderOpen, KeyRound, Save, RotateCcw, ExternalLink, Info } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import {
  ServerCommandBlock,
  ServerTestButton,
} from "@/components/mcp/ServerDiagnostics";
import * as api from "@/lib/api";
import { useSettings } from "@/stores/settings";
import { MCP_SERVER_CATALOG, getServerDisplay } from "@/lib/mcp/servers";
import { cn } from "@/lib/utils";
import type { CockpitConfig, McpServerInfo, ValidationReport } from "@/types/mcp";

export function Settings() {
  const { t } = useTranslation();
  const config = useSettings((s) => s.config);
  const load = useSettings((s) => s.load);
  const loadError = useSettings((s) => s.loadError);
  const update = useSettings((s) => s.update);
  const reset = useSettings((s) => s.reset);
  const [busy, setBusy] = useState(false);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);

  useEffect(() => {
    if (!config) {
      void load();
    }
  }, [config, load]);

  async function pickDir() {
    setBusy(true);
    try {
      const dir = await api.pickDumpDir();
      if (dir) {
        await update({ dumpPath: dir });
        toast.success(t("settings.dumpDirectoryUpdated"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function pickWorkbenchDir() {
    if (!config) {
      return;
    }
    setBusy(true);
    try {
      const dir = await api.pickWorkbenchDir();
      if (dir) {
        const patch: Partial<CockpitConfig> = {
          workbenchPath: dir,
          codeIndexHome: `${dir}\\generated\\code-index-home`,
          helpDbPath: `${dir}\\generated\\help-index\\help-index.db`,
        };
        const nextConfig = { ...config, ...patch };
        useSettings.setState({ config: nextConfig });
        await update(patch);
        setValidation(await api.validateConfig(nextConfig));
        toast.success(t("settings.workbenchDirectoryUpdated"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!config) {
      return;
    }
    setBusy(true);
    try {
      await update(config);
      setValidation(await api.validateConfig(config));
      toast.success(t("settings.settingsSaved"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("settings.saveFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function openConfigFile() {
    try {
      await api.openConfigFile();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("settings.openConfigFailed"));
    }
  }

  async function resetSettings() {
    setBusy(true);
    try {
      await reset();
      toast.success(t("settings.settingsReset"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("settings.resetFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function validatePaths() {
    if (!config) {
      return;
    }
    setBusy(true);
    try {
      const report = await api.validateConfig(config);
      setValidation(report);
      if (report.ok) {
        toast.success(t("settings.pathsValidated"));
      } else {
        toast.error(t("settings.pathsBlocked"));
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("settings.validationFailed"));
    } finally {
      setBusy(false);
    }
  }

  if (!config) {
    return (
      <div className="flex h-full flex-col">
        <PageHeader title={t("settings.title")} description={t("settings.loading")} />
        <div className="flex-1 p-6">
          <EmptyState title={t("settings.loadingSettings")} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title={t("settings.title")}
        description={t("settings.description")}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={openConfigFile}>
              <ExternalLink className="mr-2 h-4 w-4" />
              {t("settings.openConfig")}
            </Button>
            <Button variant="outline" size="sm" onClick={resetSettings} disabled={busy}>
              <RotateCcw className="mr-2 h-4 w-4" />
              {t("settings.reset")}
            </Button>
            <Button size="sm" onClick={save} disabled={busy}>
              <Save className="mr-2 h-4 w-4" />
              {t("settings.save")}
            </Button>
          </>
        }
      />

      <div className="scrollbar-thin flex-1 space-y-4 overflow-auto p-6">
        {loadError ? (
          <div className="rounded-md border border-warning/30 bg-warning/10 p-3 text-sm text-warning-foreground">
            {t("settings.fallbackNotice", { error: loadError })}
          </div>
        ) : null}
        <Card>
          <CardHeader>
            <CardTitle>{t("settings.pathsTitle")}</CardTitle>
            <CardDescription>{t("settings.pathsDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label={t("settings.field.dumpDir")} description={t("settings.field.dumpDirDescription")}>
              <div className="flex gap-2">
                <Input
                  value={config.dumpPath}
                  onChange={(e) => useSettings.setState({ config: { ...config, dumpPath: e.target.value } })}
                />
                <Button variant="outline" onClick={pickDir} disabled={busy}>
                  <FolderOpen className="h-4 w-4" />
                </Button>
              </div>
            </Field>
            <Separator />
            <Field
              label={t("settings.field.workbenchPath")}
              description={t("settings.field.workbenchPathDescription")}
            >
              <div className="flex gap-2">
                <Input
                  value={config.workbenchPath}
                  onChange={(e) =>
                    useSettings.setState({ config: { ...config, workbenchPath: e.target.value } })
                  }
                />
                <Button variant="outline" onClick={pickWorkbenchDir} disabled={busy}>
                  <FolderOpen className="h-4 w-4" />
                </Button>
              </div>
            </Field>
            <Field
              label={t("settings.field.codeIndexHome")}
              description={t("settings.field.codeIndexHomeDescription")}
            >
              <Input
                value={config.codeIndexHome}
                onChange={(e) =>
                  useSettings.setState({ config: { ...config, codeIndexHome: e.target.value } })
                }
              />
            </Field>
            <Field
              label={t("settings.field.helpDbPath")}
              description={t("settings.field.helpDbPathDescription")}
            >
              <Input
                value={config.helpDbPath}
                onChange={(e) => useSettings.setState({ config: { ...config, helpDbPath: e.target.value } })}
              />
            </Field>
            <Button variant="outline" onClick={validatePaths} disabled={busy}>
              {t("settings.validatePaths")}
            </Button>
            {validation ? <ValidationTable validation={validation} /> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="h-4 w-4" /> {t("settings.aiTitle")}
            </CardTitle>
            <CardDescription>{t("settings.aiDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label={t("settings.field.apiKey")} description={t("settings.field.apiKeyDescription")}>
              <div className="flex gap-2">
                <Input
                  type={showApiKey ? "text" : "password"}
                  autoComplete="off"
                  value={config.llm?.apiKey ?? ""}
                  onChange={(e) =>
                    useSettings.setState({
                      config: {
                        ...config,
                        llm: { ...(config.llm ?? {}), apiKey: e.target.value },
                      },
                    })
                  }
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowApiKey((prev) => !prev)}
                  aria-label={showApiKey ? t("settings.hideKey") : t("settings.showKey")}
                >
                  {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </Field>
            <Field label={t("settings.field.baseUrl")} description={t("settings.field.baseUrlDescription")}>
              <Input
                value={config.llm?.baseUrl ?? "https://api.openai.com/v1"}
                onChange={(e) =>
                  useSettings.setState({
                    config: {
                      ...config,
                      llm: { ...(config.llm ?? {}), baseUrl: e.target.value },
                    },
                  })
                }
              />
            </Field>
            <Field label={t("settings.field.model")} description={t("settings.field.modelDescription")}>
              <Input
                value={config.llm?.model ?? "gpt-4o-mini"}
                onChange={(e) =>
                  useSettings.setState({
                    config: {
                      ...config,
                      llm: { ...(config.llm ?? {}), model: e.target.value },
                    },
                  })
                }
              />
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("settings.serversTitle")}</CardTitle>
            <CardDescription>{t("settings.serversDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {MCP_SERVER_CATALOG.map((entry) => {
              const server = config.servers[entry.id] ?? {
                enabled: entry.defaultEnabled,
                command: "",
                args: [],
                env: {},
              };
              const enabled = server.enabled;
              const { name, description } = getServerDisplay(entry, t);
              const resolvedServer: McpServerInfo = {
                name: entry.id,
                description,
                status: enabled ? "stopped" : "disabled",
                version: null,
                command: server.command,
                args: server.args,
                env: server.env,
                enabled,
                lastActivity: null,
                lastError: null,
                lastErrorDetails: null,
              };
              return (
                <div
                  key={entry.id}
                  className={cn(
                    "space-y-2 rounded-md border border-border p-3",
                    !enabled && "opacity-60",
                  )}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-sm font-medium">{name}</div>
                      <p className="text-xs text-muted-foreground">{description}</p>
                    </div>
                    <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={enabled}
                        onChange={(e) => {
                          const nextServers = {
                            ...config.servers,
                            [entry.id]: { ...server, enabled: e.target.checked },
                          };
                          useSettings.setState({ config: { ...config, servers: nextServers } });
                        }}
                      />
                      <span>{enabled ? t("settings.enabled") : t("settings.disabled")}</span>
                    </label>
                  </div>
                  {enabled ? (
                    <>
                      <ServerCommandBlock server={resolvedServer} />
                      <ServerTestButton server={resolvedServer} />
                    </>
                  ) : null}
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="h-4 w-4" /> {t("settings.aboutTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm text-muted-foreground">
            <div>{t("settings.aboutVersion")}</div>
            <div>
              1c-ai-workbench:{" "}
              <a
                href="https://github.com/timoshinoleg-eng/1c-ai-workbench"
                target="_blank"
                rel="noreferrer noopener"
                className="text-primary hover:underline"
              >
                github.com/timoshinoleg-eng/1c-ai-workbench
              </a>
            </div>
            <div>{t("settings.aboutLicense")}</div>
          </CardContent>
        </Card>
      </div>
    </div>
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

function Field({
  label,
  description,
  children,
}: {
  label: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex flex-col">
        <label className="text-sm font-medium">{label}</label>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      {children}
    </div>
  );
}
