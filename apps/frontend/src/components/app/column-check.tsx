import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { useI18n } from "@/lib/i18n"
import { api } from "@/lib/api"
import type { SheetValidationResponse } from "@/types/api"

function SheetIssues({ label, sheet }: { label: string; sheet: SheetValidationResponse }) {
  const { t } = useI18n()
  if (sheet.valido) return null
  return (
    <div className="flex flex-col gap-1">
      <p className="font-medium text-red-700 dark:text-red-400">{label}</p>
      <div className="flex flex-wrap gap-1">
        {sheet.columnas_faltantes.map((c) => (
          <Badge key={c} variant="destructive">
            {c}
          </Badge>
        ))}
      </div>
      {sheet.columnas_extra.length > 0 && (
        <p className="text-muted-foreground">
          {t("columnCheck.extraColumns", { list: sheet.columnas_extra.join(", ") })}
        </p>
      )}
    </div>
  )
}

export function ColumnCheck({ uploadId }: { uploadId: string }) {
  const { t } = useI18n()
  const query = useQuery({
    queryKey: ["validate-columns", uploadId],
    queryFn: () => api.uploads.validateColumns(uploadId),
    retry: false,
  })

  if (query.isLoading) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" /> {t("columnCheck.checking")}
      </div>
    )
  }

  if (query.isError || !query.data) {
    return <p className="text-muted-foreground text-sm">{t("columnCheck.unavailable")}</p>
  }

  const { valido, facturas, items } = query.data

  if (valido) {
    const opcionales = [...facturas.columnas_opcionales_presentes, ...items.columnas_opcionales_presentes]
    return (
      <div className="flex items-start gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm">
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
        <div>
          <p className="font-medium text-emerald-700 dark:text-emerald-400">
            {t("columnCheck.validTitle")}
          </p>
          <p className="text-muted-foreground">
            {t("columnCheck.validBody", {
              optional: opcionales.length > 0 ? t("columnCheck.validOptional", { list: opcionales.join(", ") }) : "",
            })}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-red-600 dark:text-red-400" />
      <div className="flex flex-col gap-3">
        <p className="font-medium text-red-700 dark:text-red-400">{t("columnCheck.invalidTitle")}</p>
        <SheetIssues label={t("columnCheck.sheetFacturas")} sheet={facturas} />
        <SheetIssues label={t("columnCheck.sheetItems")} sheet={items} />
      </div>
    </div>
  )
}
