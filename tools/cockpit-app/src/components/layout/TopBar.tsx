import { Activity, Github, Languages } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";

export function TopBar() {
  const { t, i18n } = useTranslation();
  const next = i18n.language.startsWith("ru") ? "en" : "ru";
  const switchTitle = next === "ru" ? "Русский" : "English";
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card/40 px-4">
      <div className="flex items-center gap-2 text-sm">
        <Activity className="h-4 w-4 text-primary" />
        <span className="font-medium">{t("app.name")}</span>
        <span className="text-muted-foreground">· {t("app.tagline")}</span>
      </div>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <a
          href="https://github.com/timoshinoleg-eng/1c-ai-workbench"
          target="_blank"
          rel="noreferrer noopener"
          className="flex items-center gap-1 hover:text-foreground"
        >
          <Github className="h-3.5 w-3.5" />
          {t("app.github")}
        </a>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => void i18n.changeLanguage(next)}
          title={switchTitle}
          aria-label={`Switch language to ${switchTitle}`}
        >
          <Languages className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
