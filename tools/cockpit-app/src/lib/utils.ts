import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind classes with conflict resolution.
 * Mirrors shadcn/ui's `cn()` helper.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const EMPTY_PLACEHOLDER = "—";

/**
 * Format an ISO date for the UI. Defaults to the Russian locale to match the
 * v0.1.0 visual contract; pass an explicit locale (e.g. `i18n.language`) to
 * localize. The `EMERGENCY_PLACEHOLDER` ("—") is returned for nullish or
 * unparseable input and must be the same string in every language.
 */
export function formatTimestamp(
  iso: string | null | undefined,
  locale: string = "ru-RU",
): string {
  if (!iso) {
    return EMPTY_PLACEHOLDER;
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return EMPTY_PLACEHOLDER;
  }
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/**
 * Format a past ISO timestamp as a human-readable relative duration
 * (e.g. "2 min ago" / "только что"). Uses `Intl.RelativeTimeFormat` with
 * `numeric: "auto"` so "1 minute ago" renders as "1 минуту назад" in Russian
 * and "1 minute ago" in English. Falls back to absolute time beyond a week.
 */
export function formatRelative(
  iso: string | null | undefined,
  locale: string = "ru-RU",
  now: Date = new Date(),
): string {
  if (!iso) {
    return EMPTY_PLACEHOLDER;
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return EMPTY_PLACEHOLDER;
  }
  const diffMs = date.getTime() - now.getTime();
  const diffSec = Math.round(diffMs / 1000);
  const abs = Math.abs(diffSec);

  // `Intl.RelativeTimeFormat` thresholds: keep the largest sensible bucket.
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  if (abs < 45) {
    return rtf.format(diffSec, "second");
  }
  if (abs < 3600) {
    return rtf.format(Math.round(diffSec / 60), "minute");
  }
  if (abs < 86_400) {
    return rtf.format(Math.round(diffSec / 3600), "hour");
  }
  if (abs < 604_800) {
    return rtf.format(Math.round(diffSec / 86_400), "day");
  }
  return formatTimestamp(iso, locale);
}

/** Debounce hook helper. Used by search inputs. */
export function debounce<T extends (...args: never[]) => void>(fn: T, delay: number): T {
  let timer: ReturnType<typeof setTimeout> | null = null;
  return ((...args: Parameters<T>) => {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => fn(...args), delay);
  }) as T;
}
