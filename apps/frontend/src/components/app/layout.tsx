import { Link, Outlet } from "react-router-dom"

import { LanguageToggle } from "@/components/app/language-toggle"
import { ThemeToggle } from "@/components/app/theme-toggle"
import { useI18n } from "@/lib/i18n"

export function AppLayout() {
  const { t } = useI18n()

  return (
    <div className="min-h-svh bg-background">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3">
          <Link to="/app" className="font-semibold tracking-tight">
            AuditLake
          </Link>
          <span className="text-muted-foreground hidden text-sm sm:inline">
            {t("layout.tagline")}
          </span>
          <div className="ml-auto flex items-center gap-1">
            <Link to="/" className="text-muted-foreground px-2 text-sm hover:underline">
              {t("layout.aboutProject")}
            </Link>
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
