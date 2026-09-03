import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Loader2, Play } from "lucide-react"
import { useState } from "react"
import { Link, useParams } from "react-router-dom"
import { toast } from "sonner"

import { ColumnCheck } from "@/components/app/column-check"
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
import { useI18n } from "@/lib/i18n"
import { api } from "@/lib/api"
import { runFullPipeline, type PipelineStatus } from "@/lib/pipeline"
import type { SheetPreview } from "@/types/api"

function SheetTable({ sheet }: { sheet: SheetPreview }) {
  const { t } = useI18n()
  return (
    <div className="flex flex-col gap-2">
      <p className="text-muted-foreground text-sm">
        {t("job.layerRowCount", { total: sheet.row_count.toLocaleString(), shown: sheet.preview.length })}
      </p>
      <div className="overflow-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {sheet.columns.map((c) => (
                <TableHead key={c}>{c}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sheet.preview.map((row, i) => (
              <TableRow key={i}>
                {sheet.columns.map((c) => (
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

function LayerPreviewTable({
  uploadId,
  layer,
}: {
  uploadId: string
  layer: "bronze" | "silver"
}) {
  const { t } = useI18n()
  const query = useQuery({
    queryKey: ["layer", uploadId, layer],
    queryFn: () => api.audits.dualLayerPreview(uploadId, layer),
    retry: false,
  })

  if (query.isLoading) return <p className="text-muted-foreground text-sm">{t("job.layerLoading")}</p>
  if (query.isError) {
    return (
      <p className="text-muted-foreground text-sm">{t("job.layerNotReady", { layer })}</p>
    )
  }
  if (!query.data) return null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">{t("job.sheetFacturas")}</h3>
        <SheetTable sheet={query.data.sheets.facturas} />
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">{t("job.sheetItems")}</h3>
        <SheetTable sheet={query.data.sheets.items} />
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
  const { t } = useI18n()
  const [processing, setProcessing] = useState(false)
  const [processMsg, setProcessMsg] = useState<string | null>(null)

  const statusQuery = useQuery({
    queryKey: ["upload-status", uploadId],
    queryFn: () => api.uploads.status(uploadId!),
    enabled: !!uploadId,
    refetchInterval: (query) => (query.state.data?.status === "PROCESSING" ? 2000 : false),
  })

  function formatPipelineStatus(status: PipelineStatus): string {
    switch (status.type) {
      case "running":
        return t("job.pipelineRunning")
      case "waitingLayer":
        return t("job.pipelineWaitingLayer", { layer: status.layer, seconds: status.seconds })
      case "silverReady":
        return t("job.pipelineSilverReady")
      case "complete":
        return t("job.pipelineComplete")
      case "timeoutSilver":
        return t("job.pipelineTimeoutSilver")
      case "timeoutGold":
        return t("job.pipelineTimeoutGold")
    }
  }

  async function handleProcess() {
    if (!uploadId) return
    setProcessing(true)
    try {
      const ok = await runFullPipeline(uploadId, (status) =>
        setProcessMsg(formatPipelineStatus(status)),
      )
      if (ok) toast.success(t("job.toastPipelineComplete"))
      else toast.error(t("job.toastPipelineTimeout"))
      await queryClient.invalidateQueries({ queryKey: ["upload-status", uploadId] })
      await queryClient.invalidateQueries({ queryKey: ["layer", uploadId] })
      await queryClient.invalidateQueries({ queryKey: ["gold-summary", uploadId] })
      await queryClient.invalidateQueries({ queryKey: ["gold-query", uploadId] })
      await queryClient.invalidateQueries({ queryKey: ["gold-matrix", uploadId] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : t("job.toastPipelineError"))
    } finally {
      setProcessing(false)
    }
  }

  if (!uploadId) return null

  return (
    <div className="flex flex-col gap-4">
      <Link to="/app" className="text-muted-foreground flex w-fit items-center gap-1 text-sm hover:underline">
        <ArrowLeft className="size-3.5" /> {t("layout.back")}
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
            {t("job.process")}
          </Button>
        </div>
      </div>

      <ColumnCheck uploadId={uploadId} />

      {processMsg && <p className="text-muted-foreground text-sm">{processMsg}</p>}

      <Tabs defaultValue="gold">
        <TabsList>
          <TabsTrigger value="bronze">{t("job.tabBronze")}</TabsTrigger>
          <TabsTrigger value="silver">{t("job.tabSilver")}</TabsTrigger>
          <TabsTrigger value="gold">{t("job.tabGold")}</TabsTrigger>
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
