import { useMemo, useState } from "react";
import { ScanSearch, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { mcp } from "@/lib/mcp/client";

const SEVERITIES = ["critical", "high", "medium", "low", "info"] as const;
type Severity = (typeof SEVERITIES)[number];

interface RiskFinding {
  severity: Severity;
  category: string;
  title: string;
  object: string;
  confidence: string;
  path: string;
}

const severityVariant: Record<Severity, "destructive" | "warning" | "secondary" | "outline"> = {
  critical: "destructive",
  high: "destructive",
  medium: "warning",
  low: "secondary",
  info: "outline",
};

export function Risk() {
  const { t } = useTranslation();
  const [scanning, setScanning] = useState(false);
  const [filter, setFilter] = useState<Severity | "all">("all");
  const [findings, setFindings] = useState<RiskFinding[]>([]);
  const [error, setError] = useState<string | null>(null);

  const visibleFindings = useMemo(
    () => (filter === "all" ? findings : findings.filter((finding) => finding.severity === filter)),
    [filter, findings],
  );

  async function runScan() {
    setScanning(true);
    setError(null);
    try {
      const response = await mcp.call("1c-code-index", "risk_scan", { limit: 500 });
      if (!response.ok) {
        throw new Error(response.error ?? "risk_scan failed");
      }
      const parsed = extractFindings(response.data);
      setFindings(parsed);
      toast.success(`Risk scan returned ${parsed.length} finding(s)`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      toast.error(message);
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title={t("risk.title")}
        description={t("risk.description")}
        actions={
          <Button onClick={runScan} disabled={scanning}>
            <ScanSearch className="mr-2 h-4 w-4" />
            {scanning ? t("risk.scanning") : t("risk.runScan")}
          </Button>
        }
      />
      <div className="flex-1 space-y-4 overflow-auto scrollbar-thin p-6">
        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}
        <Card>
          <CardHeader>
            <CardTitle>{t("risk.filtersTitle")}</CardTitle>
            <CardDescription>{t("risk.filtersDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Button variant={filter === "all" ? "default" : "outline"} size="sm" onClick={() => setFilter("all")}>
                {t("risk.all")}
              </Button>
              {SEVERITIES.map((severity) => (
                <Button
                  key={severity}
                  variant={filter === severity ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilter(severity)}
                >
                  {severity}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("risk.findingsTitle")}</CardTitle>
            <CardDescription>
              {filter === "all" ? t("risk.allSeverities") : t("risk.severity", { value: filter })}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {visibleFindings.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("risk.column.severity")}</TableHead>
                    <TableHead>{t("risk.column.category")}</TableHead>
                    <TableHead>{t("risk.column.title")}</TableHead>
                    <TableHead>{t("risk.column.object")}</TableHead>
                    <TableHead>{t("risk.column.path")}</TableHead>
                    <TableHead className="text-right">{t("risk.column.confidence")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleFindings.map((finding, index) => (
                    <TableRow key={`${finding.path}-${finding.title}-${index}`}>
                      <TableCell>
                        <Badge variant={severityVariant[finding.severity]}>{finding.severity}</Badge>
                      </TableCell>
                      <TableCell>{finding.category}</TableCell>
                      <TableCell>{finding.title}</TableCell>
                      <TableCell>{finding.object}</TableCell>
                      <TableCell className="font-mono text-xs">{finding.path}</TableCell>
                      <TableCell className="text-right">{finding.confidence}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <EmptyState
                icon={ShieldAlert}
                title={findings.length ? t("risk.noMatchesFilter") : t("risk.noFindingsYet")}
                description={t("risk.noFindingsDescription")}
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function extractFindings(data: unknown): RiskFinding[] {
  const root = unwrap(data);
  const arrays = collectArrays(root, ["findings", "results", "items", "data"]);
  const source = arrays.find((items) => items.some(isRecord)) ?? [];
  return source.filter(isRecord).map((item) => ({
    severity: normalizeSeverity(item.severity),
    category: stringValue(item.category) || stringValue(item.rule) || "general",
    title: stringValue(item.title) || stringValue(item.message) || "Risk finding",
    object: stringValue(item.object) || stringValue(item.metadata) || stringValue(item.name) || "n/a",
    confidence: stringValue(item.confidence) || stringValue(item.score) || "",
    path: stringValue(item.path) || stringValue(item.file) || "",
  }));
}

function normalizeSeverity(value: unknown): Severity {
  const normalized = String(value ?? "info").toLowerCase();
  return SEVERITIES.includes(normalized as Severity) ? (normalized as Severity) : "info";
}

function unwrap(data: unknown): unknown {
  if (typeof data === "string") {
    try {
      return JSON.parse(data) as unknown;
    } catch {
      return data;
    }
  }
  if (isRecord(data) && typeof data.result === "string") {
    return unwrap(data.result);
  }
  return data;
}

function collectArrays(data: unknown, keys: string[]): unknown[][] {
  if (Array.isArray(data)) {
    return [data];
  }
  if (!isRecord(data)) {
    return [];
  }
  const arrays = keys.flatMap((key) => (Array.isArray(data[key]) ? [data[key] as unknown[]] : []));
  if (isRecord(data.data)) {
    arrays.push(...collectArrays(data.data, keys));
  }
  return arrays;
}

function stringValue(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
