import { NavLink } from "react-router-dom";
import { BookOpen, Bot, Cog, Gauge, LayoutGrid, Search, ShieldAlert, Sparkles, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/utils";

type NavItem = {
  to: string;
  key: "cockpit" | "chat" | "search" | "help" | "risk" | "settings" | "onboarding";
  icon: LucideIcon;
  exact?: boolean;
};

const NAV_ITEMS: NavItem[] = [
  { to: "/", key: "cockpit", icon: Gauge, exact: true },
  { to: "/chat", key: "chat", icon: Bot },
  { to: "/search", key: "search", icon: Search },
  { to: "/help", key: "help", icon: BookOpen },
  { to: "/risk", key: "risk", icon: ShieldAlert },
  { to: "/settings", key: "settings", icon: Cog },
  { to: "/onboarding", key: "onboarding", icon: Sparkles },
] as const;

export function Sidebar() {
  const { t } = useTranslation();
  return (
    <aside className="hidden w-56 shrink-0 flex-col border-r border-border bg-card/40 md:flex">
      <div className="flex items-center gap-2 px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <LayoutGrid className="h-4 w-4" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold">{t("app.name")}</span>
          <span className="text-xs text-muted-foreground">{t("sidebar.version")}</span>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-2">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.exact}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md border-l-2 px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "border-emerald-400 bg-primary/10 text-primary"
                    : "border-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )
              }
            >
              <Icon className="h-4 w-4" />
              {t(`nav.${item.key}`)}
            </NavLink>
          );
        })}
      </nav>
      <div className="border-t border-border px-4 py-3 text-xs text-muted-foreground">
        <div>1c-ai-workbench</div>
        <div className="opacity-60">{t("sidebar.build")}</div>
      </div>
    </aside>
  );
}
