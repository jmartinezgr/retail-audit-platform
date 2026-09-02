import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import { api } from "@/lib/api"

const ALL = "__all__"
const PAGE_SIZE = 25

export function GoldTable({ uploadId }: { uploadId: string }) {
  const [severidad, setSeveridad] = useState<string>(ALL)
  const [regla, setRegla] = useState<string>(ALL)
  const [paso, setPaso] = useState<string>(ALL)
  const [page, setPage] = useState(0)

  const summaryQuery = useQuery({
    queryKey: ["gold-summary", uploadId],
    queryFn: () => api.audits.goldSummary(uploadId),
  })

  const goldQuery = useQuery({
    queryKey: ["gold-query", uploadId, severidad, regla, paso, page],
    queryFn: () =>
      api.audits.queryGold(uploadId, {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        severidad: severidad === ALL ? undefined : severidad,
        regla: regla === ALL ? undefined : regla,
        paso: paso === ALL ? undefined : paso === "true",
      }),
  })

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
          {totalErrores.toLocaleString()} violaciones de {totalFilas.toLocaleString()}{" "}
          evaluaciones totales
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Select value={severidad} onValueChange={resetPageAnd(setSeveridad)}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Severidad" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Toda severidad</SelectItem>
            <SelectItem value="ERROR">ERROR</SelectItem>
            <SelectItem value="WARNING">WARNING</SelectItem>
          </SelectContent>
        </Select>

        <Select value={regla} onValueChange={resetPageAnd(setRegla)}>
          <SelectTrigger className="w-64">
            <SelectValue placeholder="Regla" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Toda regla</SelectItem>
            {reglas.map((r) => (
              <SelectItem key={r} value={r}>
                {r}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={paso} onValueChange={resetPageAnd(setPaso)}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Resultado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Pase o falle</SelectItem>
            <SelectItem value="false">Solo violaciones</SelectItem>
            <SelectItem value="true">Solo pasadas</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="overflow-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Factura</TableHead>
              <TableHead>Sede</TableHead>
              <TableHead>Fecha</TableHead>
              <TableHead>Regla</TableHead>
              <TableHead>Severidad</TableHead>
              <TableHead>Resultado</TableHead>
              <TableHead>Mensaje</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {goldQuery.isLoading && (
              <TableRow>
                <TableCell colSpan={7} className="text-muted-foreground text-center">
                  Cargando...
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
                    <span className="text-emerald-600 dark:text-emerald-400">OK</span>
                  ) : (
                    <span className="font-medium text-red-600 dark:text-red-400">Falla</span>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground max-w-xs truncate">
                  {row.mensaje}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-muted-foreground text-sm">
          {total > 0 ? `${from}–${to} de ${total.toLocaleString()}` : "0 resultados"}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Anterior
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={to >= total}
            onClick={() => setPage((p) => p + 1)}
          >
            Siguiente
          </Button>
        </div>
      </div>
    </div>
  )
}
