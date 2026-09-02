import {
  ArrowRight,
  Calculator,
  Database,
  FileSpreadsheet,
  Layers,
  Network,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { Link } from "react-router-dom"

import { LanguageToggle } from "@/components/app/language-toggle"
import { ThemeToggle } from "@/components/app/theme-toggle"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useI18n } from "@/lib/i18n"
import type { TranslationKey } from "@/i18n/translations"

const CAPAS: { titleKey: TranslationKey; descKey: TranslationKey; icon: typeof FileSpreadsheet }[] = [
  { titleKey: "landing.bronzeTitle", descKey: "landing.bronzeDesc", icon: FileSpreadsheet },
  { titleKey: "landing.silverTitle", descKey: "landing.silverDesc", icon: Layers },
  { titleKey: "landing.goldTitle", descKey: "landing.goldDesc", icon: ShieldCheck },
]

const STACK = ["FastAPI", "Polars", "Delta Lake", "DuckDB", "Postgres", "MinIO", "React", "TypeScript"]

export function LandingPage() {
  const { t } = useI18n()

  return (
    <div className="min-h-svh bg-background">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <span className="font-semibold tracking-tight">AuditLake</span>
          <div className="flex items-center gap-1">
            <LanguageToggle />
            <ThemeToggle />
            <Button size="sm" variant="outline" asChild className="ml-1">
              <Link to="/app">{t("landing.tryDemo")}</Link>
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl flex-col gap-20 px-4 py-8">
        <section className="flex flex-col items-center gap-6 text-center">
          <Badge variant="outline" className="gap-1.5">
            <Sparkles className="size-3" /> {t("landing.badge")}
          </Badge>
          <h1 className="max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
            {t("landing.title")}
          </h1>
          <p className="text-muted-foreground max-w-xl text-lg">{t("landing.subtitle")}</p>
          <div className="flex gap-3">
            <Button size="lg" asChild>
              <Link to="/app">
                {t("landing.tryDemo")} <ArrowRight />
              </Link>
            </Button>
          </div>
        </section>

        <section className="flex flex-col gap-6">
          <div className="text-center">
            <h2 className="text-2xl font-semibold">{t("landing.howItWorksTitle")}</h2>
            <p className="text-muted-foreground mt-1">{t("landing.howItWorksSubtitle")}</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            {CAPAS.map((capa) => (
              <Card key={capa.titleKey}>
                <CardHeader>
                  <capa.icon className="text-primary size-6" />
                  <CardTitle>{t(capa.titleKey)}</CardTitle>
                  <CardDescription>{t(capa.descKey)}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </section>

        <section className="flex flex-col gap-6">
          <div className="text-center">
            <h2 className="text-2xl font-semibold">{t("landing.validationTitle")}</h2>
            <p className="text-muted-foreground mt-1">{t("landing.validationSubtitle")}</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <Calculator className="text-primary size-6" />
                <CardTitle>{t("landing.endogenousTitle")}</CardTitle>
                <CardDescription>{t("landing.endogenousDesc")}</CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <Network className="text-primary size-6" />
                <CardTitle>{t("landing.exogenousTitle")}</CardTitle>
                <CardDescription>{t("landing.exogenousDesc")}</CardDescription>
              </CardHeader>
            </Card>
          </div>
        </section>

        <section className="flex flex-col gap-4 text-center">
          <Database className="text-primary mx-auto size-8" />
          <h2 className="text-2xl font-semibold">{t("landing.originTitle")}</h2>
          <p className="text-muted-foreground mx-auto max-w-2xl">{t("landing.originBody")}</p>
        </section>

        <section className="flex flex-col items-center gap-4">
          <h2 className="text-muted-foreground text-sm font-medium tracking-wide uppercase">
            {t("landing.stackTitle")}
          </h2>
          <div className="flex flex-wrap justify-center gap-2">
            {STACK.map((s) => (
              <Badge key={s} variant="secondary">
                {s}
              </Badge>
            ))}
          </div>
        </section>

        <section className="flex flex-col items-center gap-4 pb-8 text-center">
          <h2 className="text-2xl font-semibold">{t("landing.ctaTitle")}</h2>
          <Button size="lg" asChild>
            <Link to="/app">
              {t("landing.ctaButton")} <ArrowRight />
            </Link>
          </Button>
        </section>
      </div>
    </div>
  )
}
