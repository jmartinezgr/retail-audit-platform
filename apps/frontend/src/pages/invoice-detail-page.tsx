import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, ArrowLeft, CheckCircle2, ChevronDown, ChevronRight, Loader2, XCircle } from "lucide-react"
import { useState } from "react"
import { Link, useParams } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
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
      <span className="text-muted-foreground w-4 shrink-0 text-center">—</span>
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
          <Badge variant={row.severidad === "ERROR" ? "destructive" : "outline"}>{row.severidad}</Badge>
        </div>
        <p className="text-muted-foreground text-sm">{row.mensaje}</p>
      </div>
    </div>
  )
}

function ItemRow({
  item,
  evaluaciones,
}: {
  item: Record<string, unknown>
  evaluaciones: GoldRow[]
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const errores = evaluaciones.filter((e) => e.severidad === "ERROR" && e.paso === false).length
  const warnings = evaluaciones.filter((e) => e.severidad === "WARNING" && e.paso === false).length

  return (
    <>
      <TableRow className="hover:bg-accent/50 cursor-pointer" onClick={() => setOpen((o) => !o)}>
        <TableCell>
          {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        </TableCell>
        <TableCell className="font-mono text-xs">{formatValue(item.producto_sku)}</TableCell>
        <TableCell>{formatValue(item.cantidad)}</TableCell>
        <TableCell>{formatValue(item.precio_unitario)}</TableCell>
        <TableCell>{formatValue(item.codigo_descuento)}</TableCell>
        <TableCell>{formatValue(item.total_item)}</TableCell>
        <TableCell>
          {errores > 0 ? (
            <Badge variant="destructive">{t("invoice.itemErrors", { count: errores })}</Badge>
          ) : warnings > 0 ? (
            <Badge variant="outline">{t("invoice.itemWarnings", { count: warnings })}</Badge>
          ) : (
            <span className="text-emerald-600 dark:text-emerald-400">{t("gold.pass")}</span>
          )}
        </TableCell>
      </TableRow>
      {open && (
        <TableRow>
          <TableCell colSpan={7} className="bg-muted/30 p-0">
            <div className="px-4">
              {evaluaciones.map((row, i) => (
                <EvaluationRow key={`${row.regla}-${i}`} row={row} />
              ))}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
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

  if (query.isError || !query.data || query.data.facturas.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        {backLink}
        <p className="text-muted-foreground text-sm">{t("invoice.notFound")}</p>
      </div>
    )
  }

  const { facturas, items, evaluaciones_cabecera, evaluaciones_items, gold_ready } = query.data
  const factura = facturas[0]

  const errors = evaluaciones_cabecera.filter((e) => e.severidad === "ERROR" && e.paso === false).length
  const warnings = evaluaciones_cabecera.filter((e) => e.severidad === "WARNING" && e.paso === false).length
  const passed = evaluaciones_cabecera.filter((e) => e.paso === true).length

  const itemsPorId = new Map<number, GoldRow[]>()
  for (const row of evaluaciones_items) {
    const id = row.item_id!
    if (!itemsPorId.has(id)) itemsPorId.set(id, [])
    itemsPorId.get(id)!.push(row)
  }

  const subtotalItems = items.reduce((acc, it) => acc + (Number(it.total_item) || 0), 0)

  return (
    <div className="flex flex-col gap-4">
      {backLink}

      <div>
        <h1 className="font-mono text-xl font-semibold">
          {t("invoice.title", { numeroFactura: facturaId })}
        </h1>
      </div>

      {facturas.length > 1 && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" />
          <p className="text-muted-foreground">
            {t("invoice.duplicateWarning", { count: facturas.length })}
          </p>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{t("invoice.dataTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Field label={t("invoice.fieldSede")} value={formatValue(factura.sede_codigo)} />
          <Field label={t("invoice.fieldTrabajador")} value={formatValue(factura.trabajador_codigo)} />
          <Field label={t("invoice.fieldComprador")} value={formatValue(factura.comprador_codigo)} />
          <Field label={t("invoice.fieldFecha")} value={formatValue(factura.fecha)} />
          <Field label={t("invoice.fieldMetodoPago")} value={formatValue(factura.metodo_pago)} />
          <Field label={t("invoice.fieldIva")} value={formatValue(factura.iva_pct)} />
          <Field label={t("invoice.fieldSubtotalItems")} value={subtotalItems.toLocaleString()} />
          <Field label={t("invoice.fieldTotalFactura")} value={formatValue(factura.total_factura)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("invoice.headerEvaluationsTitle")}</CardTitle>
          {gold_ready && (
            <p className="text-muted-foreground text-sm">
              {t("invoice.evaluationsSubtitle", { errors, warnings, passed })}
            </p>
          )}
        </CardHeader>
        <CardContent>
          {gold_ready ? (
            <div className="flex flex-col">
              {evaluaciones_cabecera.map((row, i) => (
                <EvaluationRow key={`${row.regla}-${i}`} row={row} />
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">{t("invoice.goldNotReady")}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("invoice.itemsTitle")}</CardTitle>
          <p className="text-muted-foreground text-sm">{t("invoice.itemsSubtitle")}</p>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>{t("invoice.colProduct")}</TableHead>
                  <TableHead>{t("invoice.colQuantity")}</TableHead>
                  <TableHead>{t("invoice.colUnitPrice")}</TableHead>
                  <TableHead>{t("invoice.colDiscount")}</TableHead>
                  <TableHead>{t("invoice.colTotal")}</TableHead>
                  <TableHead>{t("invoice.colStatus")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item, i) => (
                  <ItemRow
                    key={`${String(item.item_id)}-${i}`}
                    item={item}
                    evaluaciones={itemsPorId.get(Number(item.item_id)) ?? []}
                  />
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
