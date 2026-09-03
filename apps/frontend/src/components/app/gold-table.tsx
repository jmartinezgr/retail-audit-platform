import { useQuery } from "@tanstack/react-query"
import { Eye } from "lucide-react"
import { type FormEvent, useState } from "react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useI18n } from "@/lib/i18n"
import { api } from "@/lib/api"
import { GoldMatrix } from "@/components/app/gold-matrix"

const ALL = "__all__"
const PAGE_SIZE = 25

export function GoldTable({ uploadId }: { uploadId: string }) {
  const { t } = useI18n()

  return (
    <Tabs defaultValue="resumen">
      <TabsList>
        <TabsTrigger value="resumen">{t("gold.viewSummary")}</TabsTrigger>
        <TabsTrigger value="detallado">{t("gold.viewDetailed")}</TabsTrigger>
      </TabsList>
      <TabsContent value="resumen">
        <GoldMatrix uploadId={uploadId} />
      </TabsContent>
      <TabsContent value="detallado">
        <GoldDetailedTable uploadId={uploadId} />
      </TabsContent>
    </Tabs>
  )
}

function GoldDetailedTable({ uploadId }: { uploadId: string }) {
  const { t } = useI18n()
  const [severidad, setSeveridad] = useState<string>(ALL)
  const [regla, setRegla] = useState<string>(ALL)
  const [paso, setPaso] = useState<string>(ALL)
  const [numeroFacturaInput, setNumeroFacturaInput] = useState("")
  const [numeroFactura, setNumeroFactura] = useState("")
  const [page, setPage] = useState(0)

  const summaryQuery = useQuery({
    queryKey: ["gold-summary", uploadId],
    queryFn: () => api.audits.goldSummary(uploadId),
    retry: false,
  })

  const goldQuery = useQuery({
    queryKey: ["gold-query", uploadId, severidad, regla, paso, numeroFactura, page],
    queryFn: () =>
      api.audits.queryGold(uploadId, {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        severidad: severidad === ALL ? undefined : severidad,
        regla: regla === ALL ? undefined : regla,
        paso: paso === ALL ? undefined : paso === "true",
        numeroFactura: numeroFactura || undefined,
      }),
    retry: false,
  })

  function handleFacturaFilterSubmit(e: FormEvent) {
    e.preventDefault()
    setNumeroFactura(numeroFacturaInput.trim())
    setPage(0)
  }

  if (summaryQuery.isError) {
    return <p className="text-muted-foreground text-sm">{t("job.layerNotReady", { layer: "gold" })}</p>
  }

  const reglas = Array.from(
    new Set((summaryQuery.data?.counts ?? []).map((c) => c.regla)),
  ).sort()

  const totalErrores = (summaryQuery.data?.counts ?? [])
    .filter((c) => c.paso === false)
    .reduce((acc, c) => acc + c.n, 0)
  const totalFilas = (summaryQuery.data?.counts ?? []).reduce((acc, c) => acc + c.n, 0)

  function resetPageAnd(setter: (v: string) => void) {
    return (v: string) => {
      setter(v)
      setPage(0)
    }
  }

  const total = goldQuery.data?.total ?? 0
  const from = total === 0 ? 0 : page * PAGE_SIZE + 1
  const to = Math.min((page + 1) * PAGE_SIZE, total)

  return (
    <div className="flex flex-col gap-3">
      {summaryQuery.data && (
        <div className="text-muted-foreground text-sm">
          {t("gold.summary", {
            violations: totalErrores.toLocaleString(),
            total: totalFilas.toLocaleString(),
          })}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <form onSubmit={handleFacturaFilterSubmit} className="flex gap-1">
          <Input
            value={numeroFacturaInput}
            onChange={(e) => setNumeroFacturaInput(e.target.value)}
            placeholder={t("gold.filterInvoicePlaceholder")}
            className="w-40"
          />
          <Button type="submit" variant="outline" size="sm">
            {t("gold.filterInvoiceApply")}
          </Button>
        </form>

        <Select value={severidad} onValueChange={resetPageAnd(setSeveridad)}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder={t("gold.filterSeverityAll")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("gold.filterSeverityAll")}</SelectItem>
            <SelectItem value="ERROR">ERROR</SelectItem>
            <SelectItem value="WARNING">WARNING</SelectItem>
          </SelectContent>
        </Select>

        <Select value={regla} onValueChange={resetPageAnd(setRegla)}>
          <SelectTrigger className="w-64">
            <SelectValue placeholder={t("gold.filterRuleAll")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("gold.filterRuleAll")}</SelectItem>
            {reglas.map((r) => (
              <SelectItem key={r} value={r}>
                {r}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={paso} onValueChange={resetPageAnd(setPaso)}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder={t("gold.filterResultAll")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("gold.filterResultAll")}</SelectItem>
            <SelectItem value="false">{t("gold.filterOnlyViolations")}</SelectItem>
            <SelectItem value="true">{t("gold.filterOnlyPassed")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="overflow-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("gold.colInvoice")}</TableHead>
              <TableHead>{t("gold.colStore")}</TableHead>
              <TableHead>{t("gold.colDate")}</TableHead>
              <TableHead>{t("gold.colRule")}</TableHead>
              <TableHead>{t("gold.colSeverity")}</TableHead>
              <TableHead>{t("gold.colResult")}</TableHead>
              <TableHead>{t("gold.colMessage")}</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {goldQuery.isLoading && (
              <TableRow>
                <TableCell colSpan={8} className="text-muted-foreground text-center">
                  {t("gold.loading")}
                </TableCell>
              </TableRow>
            )}
            {goldQuery.data?.rows.map((row, i) => (
              <TableRow key={`${row.numero_factura}-${row.regla}-${i}`}>
                <TableCell className="font-mono text-xs">{row.numero_factura}</TableCell>
                <TableCell>{row.sede_codigo}</TableCell>
                <TableCell>{row.fecha}</TableCell>
                <TableCell className="font-mono text-xs">{row.regla}</TableCell>
                <TableCell>
                  <Badge variant={row.severidad === "ERROR" ? "destructive" : "outline"}>
                    {row.severidad}
                  </Badge>
                </TableCell>
                <TableCell>
                  {row.paso === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : row.paso ? (
                    <span className="text-emerald-600 dark:text-emerald-400">{t("gold.pass")}</span>
                  ) : (
                    <span className="font-medium text-red-600 dark:text-red-400">{t("gold.fail")}</span>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground max-w-xs truncate">
                  {row.mensaje}
                </TableCell>
                <TableCell>
                  <Button variant="ghost" size="icon" className="size-7" asChild>
                    <Link
                      to={`/jobs/${uploadId}/fac/${encodeURIComponent(row.numero_factura)}`}
                      title={t("gold.viewInvoice")}
                    >
                      <Eye className="size-4" />
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-muted-foreground text-sm">
          {total > 0
            ? t("gold.pageInfo", { from, to, total: total.toLocaleString() })
            : t("gold.noResults")}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            {t("gold.previous")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={to >= total}
            onClick={() => setPage((p) => p + 1)}
          >
            {t("gold.next")}
          </Button>
        </div>
      </div>
    </div>
  )
}
