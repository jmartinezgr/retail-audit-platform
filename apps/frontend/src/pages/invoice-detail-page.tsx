import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, ArrowLeft, CheckCircle2, CircleSlash, Loader2, XCircle } from "lucide-react"
import { Link, useParams } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useI18n } from "@/lib/i18n"
import { api } from "@/lib/api"
import type { GoldRow } from "@/types/api"

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-muted-foreground text-xs">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  )
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—"
  return String(value)
}

function EvaluationRow({ row }: { row: GoldRow }) {
  const icon =
    row.paso === null ? (
      <CircleSlash className="text-muted-foreground size-4 shrink-0" />
    ) : row.paso ? (
      <CheckCircle2 className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
    ) : (
      <XCircle className="size-4 shrink-0 text-red-600 dark:text-red-400" />
    )

  return (
    <div className="flex items-start gap-3 border-b py-3 last:border-b-0">
      {icon}
      <div className="flex flex-1 flex-col gap-0.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm font-medium">{row.regla}</span>
          <Badge variant={row.severidad === "ERROR" ? "destructive" : "outline"}>
            {row.severidad}
          </Badge>
        </div>
        <p className="text-muted-foreground text-sm">{row.mensaje}</p>
      </div>
    </div>
  )
}

export function InvoiceDetailPage() {
  const { uploadId, facturaId } = useParams<{ uploadId: string; facturaId: string }>()
  const { t } = useI18n()

  const query = useQuery({
    queryKey: ["factura-detail", uploadId, facturaId],
    queryFn: () => api.audits.facturaDetail(uploadId!, facturaId!),
    enabled: !!uploadId && !!facturaId,
    retry: false,
  })

  if (!uploadId || !facturaId) return null

  if (query.isLoading) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" /> {t("invoice.loading")}
      </div>
    )
  }

  const backLink = (
    <Link
      to={`/jobs/${uploadId}`}
      className="text-muted-foreground flex w-fit items-center gap-1 text-sm hover:underline"
    >
      <ArrowLeft className="size-3.5" /> {t("invoice.back")}
    </Link>
  )

  if (query.isError || !query.data || query.data.ventas.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        {backLink}
        <p className="text-muted-foreground text-sm">{t("invoice.notFound")}</p>
      </div>
    )
  }

  const { ventas, evaluaciones, gold_ready } = query.data
  const venta = ventas[0]

  const errors = evaluaciones.filter((e) => e.severidad === "ERROR" && e.paso === false).length
  const warnings = evaluaciones.filter((e) => e.severidad === "WARNING" && e.paso === false).length
  const passed = evaluaciones.filter((e) => e.paso === true).length

  return (
    <div className="flex flex-col gap-4">
      {backLink}

      <div>
        <h1 className="font-mono text-xl font-semibold">
          {t("invoice.title", { numeroFactura: facturaId })}
        </h1>
      </div>

      {ventas.length > 1 && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" />
          <p className="text-muted-foreground">
            {t("invoice.duplicateWarning", { count: ventas.length })}
          </p>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{t("invoice.dataTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label={t("invoice.fieldSede")} value={formatValue(venta.sede_codigo)} />
          <Field label={t("invoice.fieldTrabajador")} value={formatValue(venta.trabajador_codigo)} />
          <Field label={t("invoice.fieldProducto")} value={formatValue(venta.producto_sku)} />
          <Field label={t("invoice.fieldCantidad")} value={formatValue(venta.cantidad)} />
          <Field label={t("invoice.fieldPrecioUnitario")} value={formatValue(venta.precio_unitario)} />
          <Field label={t("invoice.fieldDescuento")} value={formatValue(venta.codigo_descuento)} />
          <Field label={t("invoice.fieldTotal")} value={formatValue(venta.total)} />
          <Field label={t("invoice.fieldMetodoPago")} value={formatValue(venta.metodo_pago)} />
          <Field label={t("invoice.fieldFecha")} value={formatValue(venta.fecha)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("invoice.evaluationsTitle")}</CardTitle>
          {gold_ready && (
            <p className="text-muted-foreground text-sm">
              {t("invoice.evaluationsSubtitle", { errors, warnings, passed })}
            </p>
          )}
        </CardHeader>
        <CardContent>
          {gold_ready ? (
            <div className="flex flex-col">
              {evaluaciones.map((row, i) => (
                <EvaluationRow key={`${row.regla}-${i}`} row={row} />
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">{t("invoice.goldNotReady")}</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
