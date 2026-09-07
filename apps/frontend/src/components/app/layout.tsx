import { Menu, X } from "lucide-react"
import { useState } from "react"
import { Link, Outlet } from "react-router-dom"

import { LanguageToggle } from "@/components/app/language-toggle"
import { ThemeToggle } from "@/components/app/theme-toggle"
import { useI18n } from "@/lib/i18n"

export function AppLayout() {
  const { t } = useI18n()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="min-h-svh bg-background">
      <header className="relative border-b">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3">
          <Link to="/app" className="font-semibold tracking-tight" onClick={() => setMenuOpen(false)}>
            AuditLake
          </Link>
          <span className="text-muted-foreground hidden text-sm sm:inline">
            {t("layout.tagline")}
          </span>
          <div className="ml-auto flex items-center gap-1">
            <nav className="hidden items-center gap-1 sm:flex">
              <Link to="/app/rules" className="text-muted-foreground px-2 text-sm hover:underline">
                {t("layout.rules")}
              </Link>
              <Link to="/" className="text-muted-foreground px-2 text-sm hover:underline">
                {t("layout.aboutProject")}
              </Link>
            </nav>
            <LanguageToggle />
            <ThemeToggle />
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-label="Toggle menu"
              className="text-muted-foreground hover:bg-muted relative z-50 rounded-md p-2 sm:hidden"
            >
              {menuOpen ? <X className="size-4" /> : <Menu className="size-4" />}
            </button>
          </div>
        </div>
        {menuOpen && (
          <>
            <button
              type="button"
              aria-label="Close menu"
              className="fixed inset-0 z-40 sm:hidden"
              onClick={() => setMenuOpen(false)}
            />
            <nav className="bg-background/80 absolute inset-x-0 top-full z-50 flex flex-col gap-1 border-b p-2 backdrop-blur sm:hidden">
              <Link
                to="/app/rules"
                onClick={() => setMenuOpen(false)}
                className="hover:bg-muted rounded-md px-3 py-2 text-sm"
              >
                {t("layout.rules")}
              </Link>
              <Link
                to="/"
                onClick={() => setMenuOpen(false)}
                className="hover:bg-muted rounded-md px-3 py-2 text-sm"
              >
                {t("layout.aboutProject")}
              </Link>
            </nav>
          </>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
