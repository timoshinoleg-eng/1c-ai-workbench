/**
 * i18next bootstrap. Self-initializes on import — just `import "@/i18n"` once
 * (see `main.tsx`) and call `useTranslation()` anywhere downstream.
 *
 * Language resolution order:
 *   1. `localStorage["cockpit.lang"]` (manual switcher wins on subsequent runs)
 *   2. `navigator.language` — any `ru*` variant resolves to Russian
 *   3. English fallback
 */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import ru from "./locales/ru.json";

const STORAGE_KEY = "cockpit.lang";
const SUPPORTED = ["en", "ru"] as const;
type Supported = (typeof SUPPORTED)[number];

function detectInitialLanguage(): Supported {
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && (SUPPORTED as readonly string[]).includes(stored)) {
      return stored as Supported;
    }
    const nav = window.navigator?.language ?? "";
    if (nav.toLowerCase().startsWith("ru")) {
      return "ru";
    }
  }
  return "en";
}

if (!i18n.isInitialized) {
  void i18n.use(initReactI18next).init({
    resources: {
      en: { translation: en },
      ru: { translation: ru },
    },
    lng: detectInitialLanguage(),
    fallbackLng: "en",
    supportedLngs: [...SUPPORTED],
    interpolation: { escapeValue: false },
    returnNull: false,
  });
}

i18n.on("languageChanged", (lng) => {
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(STORAGE_KEY, lng);
    } catch {
      // localStorage may be unavailable (private mode, quota); safe to ignore.
    }
  }
  document.documentElement.lang = lng;
});

if (typeof document !== "undefined") {
  document.documentElement.lang = i18n.language;
}

export { i18n };
export type { Supported };
