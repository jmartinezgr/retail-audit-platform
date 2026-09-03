import { useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Download,
  FileText,
  Loader2,
  Scale,
  XCircle,
} from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useI18n } from "@/lib/i18n"
import { api } from "@/lib/api"
import { downloadBlobToDisk } from "@/lib/pipeline"
import type { RuleFailureBreakdown } from "@/types/api"

function StatCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof FileText
  label: string
  value: string
  tone?: "emerald" | "red" | "amber"
}) {
  const toneClass =
    tone === "emerald"
      ? "text-emerald-600 dark:text-emerald-400"
      : tone === "red"
        ? "text-red-600 dark:text-red-400"
        : tone === "amber"
          ? "text-amber-600 dark:text-amber-400"
          : "text-primary"

  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-4">
        <Icon className={`size-6 shrink-0 ${toneClass}`} />
        <div className="flex flex-col">
          <span className="text-2xl font-semibold tabular-nums">{value}</span>
          <span className="text-muted-foreground text-xs">{label}</span>
        </div>
      </CardContent>
    </Card>
  )
}

function RuleRankingRow({ rule, max }: { rule: RuleFailureBreakdown; max: number }) {
  const pct = max > 0 ? Math.round((rule.facturas_afectadas / max) * 100) : 0
  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="w-64 shrink-0 truncate font-mono text-xs" title={rule.regla}>
        {rule.regla}
      </span>
      <div className="bg-muted h-2 flex-1 overflow-hidden rounded-full">
        <div
          className={`h-full rounded-full ${rule.severidad === "ERROR" ? "bg-red-500" : "bg-amber-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-muted-foreground w-10 shrink-0 text-right text-xs tabular-nums">
        {rule.facturas_afectadas}
      </span>
    </div>
  )
}

export function Dashboard({ uploadId }: { uploadId: string }) {
  const { t } = useI18n()
  const [exporting, setExporting] = useState(false)

  const query = useQuery({
    queryKey: ["dashboard", uploadId],
    queryFn: () => api.audits.dashboard(uploadId),
    retry: false,
  })

  async function handleExport() {
    setExporting(true)
    try {
      const res = await api.audits.exportProblematic(uploadId)
      const fileRes = await fetch(res.download_url)
      const blob = await fileRes.blob()
      downloadBlobToDisk(blob, `facturas_problematicas_${uploadId.slice(0, 8)}.xlsx`)
      toast.success(t("dashboard.exportSuccess", { count: res.facturas_problematicas }))
    } catch (e) {
      toast.error(e instanceof Error ? e.message : t("dashboard.exportError"))
    } finally {
      setExporting(false)
    }
  }

  if (query.isLoading) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" /> {t("gold.loading")}
      </div>
    )
  }

  if (query.isError || !query.data) {
    return <p className="text-muted-foreground text-sm">{t("job.layerNotReady", { layer: "gold" })}</p>
  }

  const d = query.data
  const pctValidas = d.total_facturas > 0 ? Math.round((d.facturas_validas / d.total_facturas) * 100) : 0
  const pctValorValidado = d.valor_total_registrado > 0 ? Math.round((d.valor_validado / d.valor_total_registrado) * 100) : 0
  const maxAfectadas = Math.max(0, ...d.reglas.map((r) => r.facturas_afectadas))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-muted-foreground text-sm">{t("dashboard.subtitle")}</p>
        <Button onClick={handleExport} disabled={exporting} variant="outline" size="sm">
          {exporting ? <Loader2 className="animate-spin" /> : <Download />}
          {t("dashboard.exportButton")}
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard icon={FileText} label={t("dashboard.totalFacturas")} value={d.total_facturas.toLocaleString()} />
        <StatCard
          icon={CheckCircle2}
          label={t("dashboard.facturasValidas", { pct: pctValidas })}
          value={d.facturas_validas.toLocaleString()}
          tone="emerald"
        />
        <StatCard
          icon={XCircle}
          label={t("dashboard.facturasConError")}
          value={d.facturas_con_error.toLocaleString()}
          tone="red"
        />
        <StatCard
          icon={AlertTriangle}
          label={t("dashboard.facturasSoloWarning")}
          value={d.facturas_solo_warning.toLocaleString()}
          tone="amber"
        />
        <StatCard
          icon={Copy}
          label={t("dashboard.itemsDuplicados")}
          value={d.facturas_con_items_duplicados.toLocaleString()}
          tone="amber"
        />
        <StatCard
          icon={Scale}
          label={t("dashboard.totalNoCuadra")}
          value={d.facturas_con_total_no_cuadra.toLocaleString()}
          tone="amber"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("dashboard.valueTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-0.5">
              <span className="text-muted-foreground text-xs">{t("dashboard.valueTotal")}</span>
              <span className="text-xl font-semibold tabular-nums">{d.valor_total_registrado.toLocaleString()}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-muted-foreground text-xs">{t("dashboard.valueValidated")}</span>
              <span className="text-xl font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
                {d.valor_validado.toLocaleString()}
              </span>
            </div>
          </div>
          <div className="bg-muted h-2 overflow-hidden rounded-full">
            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${pctValorValidado}%` }} />
          </div>
          <p className="text-muted-foreground text-xs">{t("dashboard.valueHint", { pct: pctValorValidado })}</p>
        </CardContent>
      </Card>

      {d.reglas.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("dashboard.rulesRankingTitle")}</CardTitle>
            <p className="text-muted-foreground text-sm">{t("dashboard.rulesRankingSubtitle")}</p>
          </CardHeader>
          <CardContent className="flex flex-col">
            {d.reglas.map((r) => (
              <RuleRankingRow key={r.regla} rule={r} max={maxAfectadas} />
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
