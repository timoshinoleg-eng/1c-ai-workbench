import { useMemo, useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMcpTool } from "@/hooks/useMcpTool";
import { mcp } from "@/lib/mcp/client";
import { MCP_SERVER_CATALOG, getServerDisplay } from "@/lib/mcp/servers";
import type { McpToolResult } from "@/types/mcp";

type Mode = "text" | "grep" | "mcp";

interface SearchRow {
  path: string;
  line: string;
  snippet: string;
  score: string;
}

const DEFAULT_JSON_ARGS = "{\n  \"limit\": 20\n}";

export function Search() {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<Mode>("text");
  const [server, setServer] = useState("1c-code-index");
  const [tool, setTool] = useState("search_text");
  const [jsonArgs, setJsonArgs] = useState(DEFAULT_JSON_ARGS);
  const [result, setResult] = useState<McpToolResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const textTool = useMcpTool("1c-code-index", "search_text");
  const grepTool = useMcpTool("1c-code-index", "grep_body");
  const rows = useMemo(() => (result ? extractRows(result.data) : []), [result]);
  const loading = textTool.invoking || grepTool.invoking;

  async function submit() {
    setError(null);
    setResult(null);
    try {
      let response: McpToolResult;
      if (mode === "text") {
        response = await textTool.invokeAsync({ query: query.trim(), limit: 50 });
      } else if (mode === "grep") {
        response = await grepTool.invokeAsync({ pattern: query.trim(), language: "bsl", limit: 50 });
      } else {
        const parsedArgs = parseJsonArgs(jsonArgs);
        response = await mcp.call(server, tool.trim(), parsedArgs);
      }
      if (!response.ok) {
        throw new Error(response.error ?? "MCP tool returned an error");
      }
      setResult(response);
      toast.success(`${response.server}:${response.tool} returned in ${response.elapsedMs}ms`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      toast.error(message);
    }
  }

  const canSubmit = mode === "mcp" ? tool.trim().length > 0 : query.trim().length > 0;

  return (
    <div className="flex h-full flex-col">
      <PageHeader title={t("nav.search")} description={t("search.description") ?? "Local text, grep, and MCP tool search across the indexed 1C dump."} />
      <div className="flex-1 space-y-6 overflow-auto scrollbar-thin p-6">
        <Card>
          <CardHeader>
            <CardTitle>{t("search.queryTitle")}</CardTitle>
            <CardDescription>{t("search.queryDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
              <TabsList>
                <TabsTrigger value="text">{t("search.modes.text")}</TabsTrigger>
                <TabsTrigger value="grep">{t("search.modes.grep")}</TabsTrigger>
                <TabsTrigger value="mcp">{t("search.modes.mcp")}</TabsTrigger>
              </TabsList>
              <TabsContent value="text" className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  {t("search.callsText")}
                </p>
                <SearchInput query={query} setQuery={setQuery} onSubmit={submit} loading={loading} canSubmit={canSubmit} />
              </TabsContent>
              <TabsContent value="grep" className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  {t("search.callsGrep")}
                </p>
                <SearchInput query={query} setQuery={setQuery} onSubmit={submit} loading={loading} canSubmit={canSubmit} />
              </TabsContent>
              <TabsContent value="mcp" className="space-y-3">
                <div className="grid gap-3 md:grid-cols-[220px_1fr]">
                  <Select value={server} onValueChange={setServer}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {MCP_SERVER_CATALOG.map((entry) => (
                        <SelectItem key={entry.id} value={entry.id}>
                          {getServerDisplay(entry, t).name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input value={tool} onChange={(event) => setTool(event.target.value)} placeholder={t("search.toolPlaceholder")} />
                </div>
                <textarea
                  value={jsonArgs}
                  onChange={(event) => setJsonArgs(event.target.value)}
                  className="min-h-36 w-full rounded-md border border-input bg-background p-3 font-mono text-sm"
                  spellCheck={false}
                />
                <Button onClick={submit} disabled={!canSubmit}>
                  {t("search.runTool")}
                </Button>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("search.resultsTitle")}</CardTitle>
            <CardDescription>
              {result ? `${result.server}:${result.tool}` : error ? t("search.requestFailed") : t("search.noQueryYet")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            ) : rows.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("search.column.path")}</TableHead>
                    <TableHead>{t("search.column.line")}</TableHead>
                    <TableHead>{t("search.column.snippet")}</TableHead>
                    <TableHead className="text-right">{t("search.column.score")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row, index) => (
                    <TableRow key={`${row.path}-${row.line}-${index}`}>
                      <TableCell className="font-mono text-xs">{row.path}</TableCell>
                      <TableCell>{row.line}</TableCell>
                      <TableCell className="max-w-xl whitespace-pre-wrap">{row.snippet}</TableCell>
                      <TableCell className="text-right">{row.score}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : result ? (
              <pre className="max-h-96 overflow-auto rounded-md bg-muted p-3 text-xs">
                {JSON.stringify(result.data, null, 2)}
              </pre>
            ) : (
              <EmptyState title={t("search.emptyTitle")} description={t("search.emptyDescription")} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SearchInput({
  query,
  setQuery,
  onSubmit,
  loading,
  canSubmit,
}: {
  query: string;
  setQuery: (value: string) => void;
  onSubmit: () => Promise<void>;
  loading: boolean;
  canSubmit: boolean;
}) {
  const { t } = useTranslation();
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit();
      }}
      className="flex gap-2"
    >
      <div className="relative flex-1">
        <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("search.placeholder")}
          className="pl-9"
        />
      </div>
      <Button type="submit" disabled={!canSubmit || loading}>
        {loading ? t("search.searching") : t("search.searchButton")}
      </Button>
    </form>
  );
}

function parseJsonArgs(text: string): Record<string, unknown> {
  const trimmed = text.trim();
  if (!trimmed) {
    return {};
  }
  const parsed = JSON.parse(trimmed) as unknown;
  if (!isRecord(parsed)) {
    throw new Error("MCP args must be a JSON object");
  }
  return parsed;
}

function extractRows(data: unknown): SearchRow[] {
  const root = unwrapToolData(data);
  const candidates = collectArrays(root, ["matches", "results", "items", "data"]);
  const source = candidates.find((items) => items.some(isRecord)) ?? [];
  return source.filter(isRecord).map((item) => ({
    path: stringValue(item.file) || stringValue(item.path) || stringValue(item.object) || "n/a",
    line: lineValue(item),
    snippet: stringValue(item.snippet) || stringValue(item.text) || stringValue(item.title) || JSON.stringify(item),
    score: stringValue(item.score) || stringValue(item.rank) || stringValue(item.confidence) || "",
  }));
}

function unwrapToolData(data: unknown): unknown {
  if (typeof data === "string") {
    try {
      return JSON.parse(data) as unknown;
    } catch {
      return data;
    }
  }
  if (isRecord(data) && typeof data.result === "string") {
    return unwrapToolData(data.result);
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

function lineValue(item: Record<string, unknown>): string {
  const start = stringValue(item.line) || stringValue(item.line_start) || stringValue(item.lineStart);
  const end = stringValue(item.line_end) || stringValue(item.lineEnd);
  return end && end !== start ? `${start}-${end}` : start;
}

function stringValue(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
