import { useEffect, useMemo, useState } from "react";
import { BookOpen, FolderTree, Search } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { mcp } from "@/lib/mcp/client";

interface HelpTopic {
  id: number;
  title: string;
  name?: string;
  snippet?: string;
  content?: string;
}

export function Help() {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [topics, setTopics] = useState<HelpTopic[]>([]);
  const [results, setResults] = useState<HelpTopic[]>([]);
  const [selected, setSelected] = useState<HelpTopic | null>(null);
  const [loadingTree, setLoadingTree] = useState(true);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadTree() {
      setLoadingTree(true);
      setError(null);
      try {
        const response = await mcp.call("1c-help-index", "get_help_tree", { parent_id: 0 });
        if (!response.ok) {
          throw new Error(response.error ?? "get_help_tree failed");
        }
        if (!cancelled) {
          setTopics(extractTopics(response.data, "children"));
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) {
          setLoadingTree(false);
        }
      }
    }
    void loadTree();
    return () => {
      cancelled = true;
    };
  }, []);

  async function searchHelp() {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    setLoadingSearch(true);
    setError(null);
    try {
      const response = await mcp.call("1c-help-index", "smart_search_help", { query: query.trim(), limit: 30 });
      if (!response.ok) {
        throw new Error(response.error ?? "smart_search_help failed");
      }
      setResults(extractTopics(response.data, "results"));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingSearch(false);
    }
  }

  async function openTopic(topic: HelpTopic) {
    setSelected(topic);
    setError(null);
    try {
      const response = await mcp.call("1c-help-index", "get_help_topic", { topic_id: topic.id });
      if (!response.ok) {
        throw new Error(response.error ?? "get_help_topic failed");
      }
      setSelected(extractTopic(response.data) ?? topic);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const visibleTopics = useMemo(() => {
    if (!query.trim()) {
      return topics;
    }
    const needle = query.toLowerCase();
    return topics.filter((topic) => topic.title.toLowerCase().includes(needle));
  }, [query, topics]);

  return (
    <div className="flex h-full flex-col">
      <PageHeader title={t("nav.help")} description={t("help.description")} />
      <div className="flex flex-1 gap-4 overflow-hidden p-6">
        <Card className="w-80 shrink-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FolderTree className="h-4 w-4" />
              {t("help.topicsTitle")}
            </CardTitle>
            <CardDescription>
              {loadingTree ? t("help.loadingTree") : t("help.topicsDescription", { count: visibleTopics.length })}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <form
              className="flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                void searchHelp();
              }}
            >
              <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("help.searchPlaceholder")} />
              <Button type="submit" size="sm" disabled={loadingSearch || !query.trim()} aria-label={t("help.searchAria")}>
                <Search className="h-4 w-4" />
              </Button>
            </form>
            {error ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
                {error}
              </div>
            ) : null}
            {loadingTree ? (
              <EmptyState icon={BookOpen} title={t("help.loadingTree")} />
            ) : visibleTopics.length ? (
              <div className="max-h-[calc(100vh-270px)] space-y-1 overflow-auto pr-1">
                {visibleTopics.map((topic) => (
                  <button
                    key={topic.id}
                    type="button"
                    onClick={() => void openTopic(topic)}
                    className="w-full rounded-md border border-border px-3 py-2 text-left text-sm hover:bg-accent"
                  >
                    {topic.title}
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={BookOpen}
                title={t("help.emptyTitle")}
                description={t("help.emptyDescription")}
              />
            )}
          </CardContent>
        </Card>

        <Card className="flex-1 overflow-hidden">
          <CardHeader>
            <CardTitle>{t("help.contentTitle")}</CardTitle>
            <CardDescription>
              {selected
                ? selected.title
                : results.length
                  ? t("help.resultsCount", { count: results.length })
                  : t("help.contentPlaceholder")}
            </CardDescription>
          </CardHeader>
          <CardContent className="max-h-[calc(100vh-180px)] overflow-auto">
            {results.length && !selected ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("help.column.topic")}</TableHead>
                    <TableHead>{t("help.column.snippet")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.map((topic) => (
                    <TableRow key={topic.id} onClick={() => void openTopic(topic)} className="cursor-pointer">
                      <TableCell>{topic.title}</TableCell>
                      <TableCell>{topic.snippet ?? ""}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : selected ? (
              <article className="prose prose-sm max-w-none dark:prose-invert">
                {selected.content ? (
                  <div dangerouslySetInnerHTML={{ __html: selected.content }} />
                ) : (
                  <p>{selected.snippet ?? selected.title}</p>
                )}
              </article>
            ) : (
              <EmptyState title={t("help.noTopicSelected")} description={t("help.noTopicSelectedDescription")} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function extractTopics(data: unknown, key: "children" | "results"): HelpTopic[] {
  const root = unwrap(data);
  const container = isRecord(root) && isRecord(root.data) ? root.data : root;
  const rows = isRecord(container) && Array.isArray(container[key]) ? container[key] : [];
  return rows.filter(isRecord).map((row, index) => ({
    id: Number(row.id ?? row.topic_id ?? index),
    title: String(row.title ?? row.name ?? row.caption ?? `Topic ${index + 1}`),
    name: row.name ? String(row.name) : undefined,
    snippet: row.snippet ? String(row.snippet) : undefined,
    content: row.content ? String(row.content) : undefined,
  }));
}

function extractTopic(data: unknown): HelpTopic | null {
  const root = unwrap(data);
  const topic = isRecord(root) && isRecord(root.data) ? root.data : root;
  if (!isRecord(topic)) {
    return null;
  }
  return {
    id: Number(topic.id ?? topic.topic_id ?? 0),
    title: String(topic.title ?? topic.name ?? "Topic"),
    snippet: topic.snippet ? String(topic.snippet) : undefined,
    content: String(topic.html ?? topic.content_html ?? topic.content ?? topic.text ?? ""),
  };
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
