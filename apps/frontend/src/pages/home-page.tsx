import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Loader2, Upload, Wand2 } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { StatusBadge } from "@/components/app/status-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api, uploadFile } from "@/lib/api"
import { downloadBlobToDisk } from "@/lib/pipeline"

export function HomePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const uploadsQuery = useQuery({
    queryKey: ["uploads"],
    queryFn: () => api.uploads.list(50),
    refetchInterval: 4000,
  })

  const [filas, setFilas] = useState(1000)
  const [errorRate, setErrorRate] = useState(0.1)
  const [generating, setGenerating] = useState(false)

  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)

  async function handleGenerate() {
    setGenerating(true)
    try {
      const gen = await api.demo.generateExcel({ filas, error_rate: errorRate })
      const filename = `demo_${filas}filas_${Math.round(errorRate * 100)}pct.xlsx`

      const fileRes = await fetch(gen.download_url)
      const blob = await fileRes.blob()
      downloadBlobToDisk(blob, filename)

      const uploadId = await uploadFile(blob, filename)
      toast.success(
        `Generadas ${gen.filas_totales} filas, ${gen.filas_con_error} con error inyectado`,
      )
      await queryClient.invalidateQueries({ queryKey: ["uploads"] })
      navigate(`/jobs/${uploadId}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error generando el excel")
    } finally {
      setGenerating(false)
    }
  }

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    try {
      const uploadId = await uploadFile(file, file.name)
      toast.success("Excel subido")
      await queryClient.invalidateQueries({ queryKey: ["uploads"] })
      navigate(`/jobs/${uploadId}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error subiendo el archivo")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wand2 className="size-4" /> Generar datos sintéticos
            </CardTitle>
            <CardDescription>
              Filas de venta contra los catálogos reales, con errores inyectados a propósito.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="filas">Filas (hasta 50,000)</Label>
                <Input
                  id="filas"
                  type="number"
                  min={1}
                  max={50000}
                  value={filas}
                  onChange={(e) => setFilas(Number(e.target.value))}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="errorRate">Tasa de error (0–1)</Label>
                <Input
                  id="errorRate"
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={errorRate}
                  onChange={(e) => setErrorRate(Number(e.target.value))}
                />
              </div>
            </div>
            <Button onClick={handleGenerate} disabled={generating}>
              {generating ? <Loader2 className="animate-spin" /> : <Wand2 />}
              Generar y subir
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="size-4" /> Subir un excel
            </CardTitle>
            <CardDescription>
              Sube tu propio archivo de ventas para auditarlo.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Input
              type="file"
              accept=".xlsx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <Button onClick={handleUpload} disabled={!file || uploading} variant="secondary">
              {uploading ? <Loader2 className="animate-spin" /> : <Upload />}
              Subir excel
            </Button>
          </CardContent>
        </Card>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Uploads recientes</h2>
        {uploadsQuery.isLoading && <p className="text-muted-foreground text-sm">Cargando...</p>}
        {uploadsQuery.data && uploadsQuery.data.uploads.length === 0 && (
          <p className="text-muted-foreground text-sm">
            Todavía no hay uploads. Genera datos o sube un excel arriba.
          </p>
        )}
        <div className="grid gap-2">
          {uploadsQuery.data?.uploads.map((u) => (
            <button
              key={u.upload_id}
              onClick={() => navigate(`/jobs/${u.upload_id}`)}
              className="hover:bg-muted/50 flex items-center justify-between rounded-lg border px-4 py-3 text-left text-sm transition-colors"
            >
              <div className="flex flex-col gap-0.5">
                <span className="font-medium">{u.filename}</span>
                <span className="text-muted-foreground text-xs">{u.upload_id}</span>
              </div>
              <StatusBadge status={u.status} />
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
