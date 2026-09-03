import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
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
import type { GoldMatrixRow } from "@/types/api"

const PAGE_SIZE = 25

function StatusIcon({ row }: { row: GoldMatrixRow }) {
  if (row.paso === null) return <span className="text-muted-foreground">—</span>
  if (row.paso) return <CheckCircle2 className="mx-auto size-4 text-emerald-600 dark:text-emerald-400" />
  if (row.severidad === "ERROR") return <XCircle className="mx-auto size-4 text-red-600 dark:text-red-400" />
  return <AlertTriangle className="mx-auto size-4 text-amber-600 dark:text-amber-400" />
}

export function GoldMatrix({ uploadId }: { uploadId: string }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [page, setPage] = useState(0)

  const query = useQuery({
    queryKey: ["gold-matrix", uploadId, page],
    queryFn: () => api.audits.goldMatrix(uploadId, PAGE_SIZE, page * PAGE_SIZE),
    retry: false,
  })

  if (query.isError) {
    return <p className="text-muted-foreground text-sm">{t("job.layerNotReady", { layer: "gold" })}</p>
  }

  const rows = query.data?.rows ?? []
  const reglas = Array.from(new Set(rows.map((r) => r.regla))).sort()

  const porFactura = new Map<string, { sede_codigo: string; fecha: string; celdas: Map<string, GoldMatrixRow> }>()
  for (const row of rows) {
    if (!porFactura.has(row.numero_factura)) {
      porFactura.set(row.numero_factura, { sede_codigo: row.sede_codigo, fecha: row.fecha, celdas: new Map() })
    }
    porFactura.get(row.numero_factura)!.celdas.set(row.regla, row)
  }

  const total = query.data?.total ?? 0
  const from = total === 0 ? 0 : page * PAGE_SIZE + 1
  const to = Math.min((page + 1) * PAGE_SIZE, porFactura.size + page * PAGE_SIZE)

  return (
    <div className="flex flex-col gap-3">
      <p className="text-muted-foreground text-sm">{t("gold.matrixHint")}</p>

      <div className="text-muted-foreground flex flex-wrap items-center gap-4 text-xs">
        <span className="flex items-center gap-1.5">
          <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400" /> {t("gold.legendPass")}
        </span>
        <span className="flex items-center gap-1.5">
          <AlertTriangle className="size-3.5 text-amber-600 dark:text-amber-400" /> {t("gold.legendWarningFail")}
        </span>
        <span className="flex items-center gap-1.5">
          <XCircle className="size-3.5 text-red-600 dark:text-red-400" /> {t("gold.legendErrorFail")}
        </span>
      </div>

      <div className="overflow-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="bg-background sticky left-0 align-bottom">{t("gold.colInvoice")}</TableHead>
              <TableHead className="align-bottom">{t("gold.colStore")}</TableHead>
              {reglas.map((r) => (
                <TableHead key={r} className="w-8 px-0 text-center align-bottom" title={r}>
                  <div
                    className="mx-auto w-fit pb-1 font-mono text-[0.65rem] whitespace-nowrap"
                    style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
                  >
                    {r}
                  </div>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {query.isLoading && (
              <TableRow>
                <TableCell colSpan={2 + reglas.length} className="text-muted-foreground text-center">
                  {t("gold.loading")}
                </TableCell>
              </TableRow>
            )}
            {Array.from(porFactura.entries()).map(([numeroFactura, info]) => (
              <TableRow
                key={numeroFactura}
                className="hover:bg-accent/50 cursor-pointer"
                onClick={() => navigate(`/jobs/${uploadId}/fac/${encodeURIComponent(numeroFactura)}`)}
              >
                <TableCell className="bg-background sticky left-0 font-mono text-xs">{numeroFactura}</TableCell>
                <TableCell>{info.sede_codigo}</TableCell>
                {reglas.map((r) => (
                  <TableCell key={r} className="text-center">
                    {info.celdas.has(r) ? <StatusIcon row={info.celdas.get(r)!} /> : null}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-muted-foreground text-sm">
          {total > 0 ? t("gold.pageInfo", { from, to, total: total.toLocaleString() }) : t("gold.noResults")}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
            {t("gold.previous")}
          </Button>
          <Button variant="outline" size="sm" disabled={to >= total} onClick={() => setPage((p) => p + 1)}>
            {t("gold.next")}
          </Button>
        </div>
      </div>
    </div>
  )
}
