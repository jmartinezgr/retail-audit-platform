import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"

export function ColumnCheck({ uploadId }: { uploadId: string }) {
  const query = useQuery({
    queryKey: ["validate-columns", uploadId],
    queryFn: () => api.uploads.validateColumns(uploadId),
    retry: false,
  })

  if (query.isLoading) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" /> Revisando columnas del excel...
      </div>
    )
  }

  if (query.isError || !query.data) {
    return (
      <p className="text-muted-foreground text-sm">
        No se pudo revisar el archivo todavía.
      </p>
    )
  }

  const { valido, columnas_faltantes, columnas_extra, columnas_opcionales_presentes } =
    query.data

  if (valido) {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm">
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
        <div>
          <p className="font-medium text-emerald-700 dark:text-emerald-400">
            Columnas correctas
          </p>
          <p className="text-muted-foreground">
            Todas las columnas esperadas están presentes
            {columnas_opcionales_presentes.length > 0 && (
              <> (incluye opcionales: {columnas_opcionales_presentes.join(", ")})</>
            )}
            . Listo para procesar.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-red-600 dark:text-red-400" />
      <div className="flex flex-col gap-1.5">
        <p className="font-medium text-red-700 dark:text-red-400">
          Faltan columnas obligatorias
        </p>
        <div className="flex flex-wrap gap-1">
          {columnas_faltantes.map((c) => (
            <Badge key={c} variant="destructive">
              {c}
            </Badge>
          ))}
        </div>
        {columnas_extra.length > 0 && (
          <p className="text-muted-foreground">
            Columnas no reconocidas en el archivo: {columnas_extra.join(", ")}
          </p>
        )}
      </div>
    </div>
  )
}
