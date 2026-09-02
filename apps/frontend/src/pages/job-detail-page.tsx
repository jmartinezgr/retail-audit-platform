import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Loader2, Play } from "lucide-react"
import { useState } from "react"
import { Link, useParams } from "react-router-dom"
import { toast } from "sonner"

import { GoldTable } from "@/components/app/gold-table"
import { StatusBadge } from "@/components/app/status-badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api } from "@/lib/api"
import { runFullPipeline } from "@/lib/pipeline"

function LayerPreviewTable({
  uploadId,
  layer,
}: {
  uploadId: string
  layer: "bronze" | "silver"
}) {
  const query = useQuery({
    queryKey: ["layer", uploadId, layer],
    queryFn: () => api.audits.layerPreview(uploadId, layer),
    retry: false,
  })

  if (query.isLoading) return <p className="text-muted-foreground text-sm">Cargando...</p>
  if (query.isError) {
    return (
      <p className="text-muted-foreground text-sm">
        Todavía no existe la tabla "{layer}" para este upload. Procesa el pipeline primero.
      </p>
    )
  }
  if (!query.data) return null

  return (
    <div className="flex flex-col gap-2">
      <p className="text-muted-foreground text-sm">
        {query.data.row_count.toLocaleString()} filas totales, mostrando {query.data.preview.length}
      </p>
      <div className="overflow-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {query.data.columns.map((c) => (
                <TableHead key={c}>{c}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {query.data.preview.map((row, i) => (
              <TableRow key={i}>
                {query.data!.columns.map((c) => (
                  <TableCell key={c} className="font-mono text-xs">
                    {formatCell(row[c])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return ""
  if (Array.isArray(value)) return value.join(", ")
  return String(value)
}

export function JobDetailPage() {
  const { uploadId } = useParams<{ uploadId: string }>()
  const queryClient = useQueryClient()
  const [processing, setProcessing] = useState(false)
  const [processMsg, setProcessMsg] = useState<string | null>(null)

  const statusQuery = useQuery({
    queryKey: ["upload-status", uploadId],
    queryFn: () => api.uploads.status(uploadId!),
    enabled: !!uploadId,
    refetchInterval: (query) => (query.state.data?.status === "PROCESSING" ? 2000 : false),
  })

  async function handleProcess() {
    if (!uploadId) return
    setProcessing(true)
    try {
      const ok = await runFullPipeline(uploadId, setProcessMsg)
      if (ok) toast.success("Pipeline completo")
      else toast.error("El pipeline no terminó a tiempo, revisa el estado")
      await queryClient.invalidateQueries({ queryKey: ["upload-status", uploadId] })
      await queryClient.invalidateQueries({ queryKey: ["layer", uploadId] })
      await queryClient.invalidateQueries({ queryKey: ["gold-summary", uploadId] })
      await queryClient.invalidateQueries({ queryKey: ["gold-query", uploadId] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error corriendo el pipeline")
    } finally {
      setProcessing(false)
    }
  }

  if (!uploadId) return null

  return (
    <div className="flex flex-col gap-4">
      <Link to="/" className="text-muted-foreground flex w-fit items-center gap-1 text-sm hover:underline">
        <ArrowLeft className="size-3.5" /> Volver
      </Link>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{statusQuery.data?.filename ?? uploadId}</h1>
          <p className="text-muted-foreground font-mono text-xs">{uploadId}</p>
        </div>
        <div className="flex items-center gap-3">
          {statusQuery.data && <StatusBadge status={statusQuery.data.status} />}
          <Button onClick={handleProcess} disabled={processing}>
            {processing ? <Loader2 className="animate-spin" /> : <Play />}
            Procesar (bronze → silver → gold)
          </Button>
        </div>
      </div>

      {processMsg && <p className="text-muted-foreground text-sm">{processMsg}</p>}

      <Tabs defaultValue="gold">
        <TabsList>
          <TabsTrigger value="bronze">Bronze</TabsTrigger>
          <TabsTrigger value="silver">Silver</TabsTrigger>
          <TabsTrigger value="gold">Gold</TabsTrigger>
        </TabsList>
        <TabsContent value="bronze">
          <LayerPreviewTable uploadId={uploadId} layer="bronze" />
        </TabsContent>
        <TabsContent value="silver">
          <LayerPreviewTable uploadId={uploadId} layer="silver" />
        </TabsContent>
        <TabsContent value="gold">
          <GoldTable uploadId={uploadId} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
