import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-card/30 px-6 py-12 text-center">
      {Icon ? <Icon className="h-10 w-10 text-muted-foreground" /> : null}
      <div>
        <p className="text-base font-medium">{title}</p>
        {description ? (
          <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
