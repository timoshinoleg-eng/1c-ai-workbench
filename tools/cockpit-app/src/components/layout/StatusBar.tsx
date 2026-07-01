import { useTranslation } from "react-i18next";

import { useMcpServers } from "@/hooks/useMcpServer";
import { useIndexStatusQuery } from "@/hooks/useIndexStatus";
import { useSettings } from "@/stores/settings";
import { formatRelative } from "@/lib/utils";

export function StatusBar() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language.startsWith("ru") ? "ru-RU" : "en-US";
  const { data: servers } = useMcpServers();
  const { data: status } = useIndexStatusQuery();
  const config = useSettings((s) => s.config);

  const running = servers?.filter((s) => s.status === "running").length ?? 0;
  const total = servers?.length ?? 0;
  const dumpPath = config?.dumpPath ?? status?.dumpPath ?? "—";
  const lastActivity = servers
    ?.map((s) => s.lastActivity)
    .filter((x): x is string => Boolean(x))
    .sort()
    .pop();

  return (
    <footer className="flex h-8 shrink-0 items-center justify-between border-t border-border bg-card/40 px-4 text-xs text-muted-foreground">
      <div className="flex items-center gap-4">
        <span>
          {t("statusbar.dump")} <span className="text-foreground">{dumpPath}</span>
        </span>
        <span>
          {t("statusbar.servers")}{" "}
          <span className="text-foreground">
            {running}/{total}
          </span>
        </span>
        {status ? (
          <span>
            {t("statusbar.index")}{" "}
            <span className="text-foreground">
              {status.indexFileCount.toLocaleString(locale)} files
            </span>
          </span>
        ) : null}
      </div>
      <div className="flex items-center gap-4">
        <span>
          {t("statusbar.lastActivity")} {formatRelative(lastActivity ?? null, locale)}
        </span>
      </div>
    </footer>
  );
}
