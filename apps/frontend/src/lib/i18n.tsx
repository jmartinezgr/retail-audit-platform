import { createContext, useContext, useEffect, useState, type ReactNode } from "react"

import { translations, type Locale, type TranslationKey } from "@/i18n/translations"

const STORAGE_KEY = "auditlake_locale"

type Vars = Record<string, string | number>

type I18nContextValue = {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: TranslationKey, vars?: Vars) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function getInitialLocale(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === "en" || stored === "es") return stored
  } catch {
    // localStorage bloqueado - seguimos con el default
  }
  return "en"
}

function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in vars ? String(vars[key]) : match,
  )
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(getInitialLocale)

  useEffect(() => {
    document.documentElement.lang = locale
    try {
      localStorage.setItem(STORAGE_KEY, locale)
    } catch {
      // no persiste entre sesiones, pero no rompe nada en esta
    }
  }, [locale])

  function setLocale(next: Locale) {
    setLocaleState(next)
  }

  function t(key: TranslationKey, vars?: Vars): string {
    const template = translations[locale][key] ?? translations.en[key] ?? key
    return interpolate(template, vars)
  }

  return <I18nContext.Provider value={{ locale, setLocale, t }}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error("useI18n debe usarse dentro de I18nProvider")
  return ctx
}
