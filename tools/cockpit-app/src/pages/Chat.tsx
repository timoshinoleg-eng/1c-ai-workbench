import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Bot, Send, Square, User2, Wrench } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import * as api from "@/lib/api";

type DisplayTurn = {
  id: string;
  role: "user" | "assistant" | "tool";
  text: string;
  toolName?: string;
};

const SUGGESTIONS_RU = [
  "Где считается сумма в документе продажи?",
  "Какие объекты связаны с контрагентами?",
  "Найди функцию, которая записывает движения регистра остатков.",
  "Что делает обработка ЗагрузкаКурсовВалют?",
];

const SUGGESTIONS_EN = [
  "Where is the total amount calculated in the sales document?",
  "Which objects are linked to counterparties?",
  "Find the function that writes balance register movements.",
  "What does the CurrencyRatesLoad processor do?",
];

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function Chat() {
  const { t, i18n } = useTranslation();
  const isRu = i18n.language?.toLowerCase().startsWith("ru");
  const suggestions = isRu ? SUGGESTIONS_RU : SUGGESTIONS_EN;

  const [history, setHistory] = useState<api.ChatMessage[]>([]);
  const [turns, setTurns] = useState<DisplayTurn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [turns, busy]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    const userTurn: DisplayTurn = { id: newId(), role: "user", text: trimmed };
    const nextHistory: api.ChatMessage[] = [
      ...history,
      { role: "user", content: trimmed },
    ];
    setTurns((prev) => [...prev, userTurn]);
    setHistory(nextHistory);
    setInput("");
    setBusy(true);

    try {
      const response = await api.chatSend(nextHistory);
      for (const turn of response.turns) {
        if (turn.role === "tool") {
          setTurns((prev) => [
            ...prev,
            {
              id: newId(),
              role: "tool",
              text: turn.toolResult ?? "",
              toolName: turn.toolName,
            },
          ]);
        } else {
          setTurns((prev) => [
            ...prev,
            {
              id: newId(),
              role: turn.role === "assistant" ? "assistant" : "assistant",
              text: turn.content,
            },
          ]);
        }
      }
      setHistory((prev) => [
        ...prev,
        { role: "assistant", content: response.finalText },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      toast.error(message);
      setTurns((prev) => [
        ...prev,
        {
          id: newId(),
          role: "assistant",
          text: isRu
            ? `Ошибка при обращении к модели: ${message}`
            : `Model request failed: ${message}`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  function stop() {
    // No-op placeholder: the Tauri call is single-shot, no streaming.
    // Surfaced as a disabled button while busy=true.
    setBusy(false);
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title={t("chat.title", "Chat")}
        description={t(
          "chat.description",
          "Talk to a local AI assistant. The model can search the indexed 1C dump and answer with file references.",
        )}
      />

      <div className="flex-1 overflow-hidden px-6 py-4">
        <Card className="flex h-full flex-col">
          <CardHeader className="border-b">
            <CardTitle className="flex items-center gap-2 text-base">
              <Bot className="h-4 w-4" />
              {t("chat.session", "1C AI assistant")}
            </CardTitle>
            <CardDescription>
              {t(
                "chat.apiHint",
                "Configure the API key in Settings → AI. The model can call 1c-code-index, 1c-skills, 1c-help-index.",
              )}
            </CardDescription>
          </CardHeader>

          <CardContent className="flex flex-1 flex-col gap-3 p-0">
            <div
              ref={scrollRef}
              className="flex-1 overflow-y-auto px-4 py-4"
              data-testid="chat-scroll"
            >
              {turns.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-muted-foreground">
                  <Bot className="h-10 w-10 opacity-50" />
                  <p className="max-w-md text-sm">
                    {t(
                      "chat.empty",
                      "Задайте вопрос по выгрузке 1С. Например: «Где считается сумма в документе продажи?»",
                    )}
                  </p>
                  <div className="grid w-full max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2">
                    {suggestions.map((s) => (
                      <Button
                        key={s}
                        variant="outline"
                        className="h-auto whitespace-normal text-left text-sm"
                        onClick={() => send(s)}
                        disabled={busy}
                      >
                        {s}
                      </Button>
                    ))}
                  </div>
                  <p className="mt-2 text-xs">
                    {t("chat.noApi", "API key not configured?")}{" "}
                    <Link to="/settings" className="underline">
                      {t("chat.openSettings", "Open Settings → AI")}
                    </Link>
                  </p>
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {turns.map((turn) => (
                    <TurnBubble key={turn.id} turn={turn} />
                  ))}
                  {busy ? (
                    <div className="flex items-center gap-2 self-start rounded-lg border bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
                      <Bot className="h-4 w-4 animate-pulse" />
                      {t("chat.thinking", "Думаю...")}
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            <div className="border-t p-3">
              <form
                className="flex items-end gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  void send(input);
                }}
              >
                <textarea
                  className="min-h-[60px] flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder={t(
                    "chat.placeholder",
                    "Спросить про 1С…",
                  )}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void send(input);
                    }
                  }}
                  disabled={busy}
                />
                {busy ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={stop}
                    disabled
                    aria-label={t("chat.stop", "Остановить")}
                  >
                    <Square className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button
                    type="submit"
                    disabled={!input.trim()}
                    aria-label={t("chat.send", "Отправить")}
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                )}
              </form>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function TurnBubble({ turn }: { turn: DisplayTurn }) {
  const { t } = useTranslation();
  if (turn.role === "user") {
    return (
      <div className="flex items-start gap-2 self-end max-w-[85%] flex-row-reverse">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <User2 className="h-4 w-4" />
        </div>
        <div className="rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground whitespace-pre-wrap break-words">
          {turn.text}
        </div>
      </div>
    );
  }
  if (turn.role === "tool") {
    return (
      <div className="flex items-start gap-2 self-start max-w-[85%]">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Wrench className="h-4 w-4" />
        </div>
        <div className="rounded-lg border bg-muted/40 px-3 py-2 text-xs">
          <div className="mb-1 font-medium text-muted-foreground">
            {t("chat.toolCall", "Инструмент")}:{" "}
            <code className="rounded bg-background px-1">{turn.toolName}</code>
          </div>
          <pre className="max-h-60 overflow-y-auto whitespace-pre-wrap break-words font-mono text-[11px] text-foreground/80">
            {turn.text}
          </pre>
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-2 self-start max-w-[85%]">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Bot className="h-4 w-4" />
      </div>
      <div className="rounded-lg border bg-card px-3 py-2 text-sm whitespace-pre-wrap break-words">
        {turn.text}
      </div>
    </div>
  );
}
