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
import { REGLAS_CABECERA, REGLAS_ITEM, type RuleCatalogEntry } from "@/data/rules-catalog"
import { useI18n } from "@/lib/i18n"
import type { TranslationKey } from "@/i18n/translations"

const CAPAS: { titleKey: TranslationKey; descKey: TranslationKey; icon: typeof FileSpreadsheet }[] = [
  { titleKey: "landing.bronzeTitle", descKey: "landing.bronzeDesc", icon: FileSpreadsheet },
  { titleKey: "landing.silverTitle", descKey: "landing.silverDesc", icon: Layers },
  { titleKey: "landing.goldTitle", descKey: "landing.goldDesc", icon: ShieldCheck },
]

const STACK = ["FastAPI", "Polars", "Delta Lake", "DuckDB", "Postgres", "MinIO", "React", "TypeScript"]

function RuleRow({ rule }: { rule: RuleCatalogEntry }) {
  const { t } = useI18n()
  return (
    <div className="flex flex-col gap-1 border-b py-3 last:border-b-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-medium">{rule.nombre}</span>
        <Badge
          variant="outline"
          className={
            rule.severidad === "ERROR"
              ? "border-red-500/40 text-red-700 dark:text-red-400"
              : "border-amber-500/40 text-amber-700 dark:text-amber-400"
          }
        >
          {rule.severidad}
        </Badge>
        <Badge variant="outline" className="text-muted-foreground font-normal">
          {rule.tipo === "endogena" ? t("landing.ruleTypeEndogenous") : t("landing.ruleTypeExogenous")}
        </Badge>
      </div>
      <p className="text-muted-foreground text-sm">{t(rule.descKey)}</p>
    </div>
  )
}

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

        <section className="flex flex-col gap-6">
          <div className="text-center">
            <h2 className="text-2xl font-semibold">{t("landing.rulesTitle")}</h2>
            <p className="text-muted-foreground mt-1">{t("landing.rulesSubtitle")}</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t("landing.rulesHeaderGroup")}</CardTitle>
              </CardHeader>
              <div className="flex flex-col px-6 pb-6">
                {REGLAS_CABECERA.map((rule) => (
                  <RuleRow key={rule.nombre} rule={rule} />
                ))}
              </div>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t("landing.rulesItemGroup")}</CardTitle>
              </CardHeader>
              <div className="flex flex-col px-6 pb-6">
                {REGLAS_ITEM.map((rule) => (
                  <RuleRow key={rule.nombre} rule={rule} />
                ))}
              </div>
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
