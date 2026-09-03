import { api } from "@/lib/api"

export type PipelineStatus =
  | { type: "running" }
  | { type: "waitingLayer"; layer: "silver" | "gold"; seconds: number }
  | { type: "silverReady" }
  | { type: "complete" }
  | { type: "timeoutSilver" }
  | { type: "timeoutGold" }

/**
 * El status del upload no distingue "silver ya terminó" de "silver
 * todavía corriendo" (ambos se ven PROCESSING) - así que en vez de
 * adivinar con un timeout, esperamos a que la capa exista de verdad
 * consultando su endpoint hasta que responda 200.
 */
async function waitForLayer(
  uploadId: string,
  layer: "silver" | "gold",
  onStatus: (status: PipelineStatus) => void,
  timeoutMs = 120_000,
  intervalMs = 800,
): Promise<boolean> {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      if (layer === "gold") await api.audits.goldPreview(uploadId)
      else await api.audits.dualLayerPreview(uploadId, layer)
      return true
    } catch {
      const elapsed = Math.round((Date.now() - start) / 1000)
      onStatus({ type: "waitingLayer", layer, seconds: elapsed })
      await new Promise((r) => setTimeout(r, intervalMs))
    }
  }
  return false
}

export async function runFullPipeline(
  uploadId: string,
  onStatus: (status: PipelineStatus) => void,
): Promise<boolean> {
  onStatus({ type: "running" })
  await api.audits.run(uploadId)

  const silverReady = await waitForLayer(uploadId, "silver", onStatus)
  if (!silverReady) {
    onStatus({ type: "timeoutSilver" })
    return false
  }

  onStatus({ type: "silverReady" })
  await api.audits.runGold(uploadId)

  const goldReady = await waitForLayer(uploadId, "gold", onStatus)
  onStatus({ type: goldReady ? "complete" : "timeoutGold" })
  return goldReady
}

/**
 * Re-corre solo gold (silver ya existe) - lee el estado ACTUAL de los
 * catálogos + reglas dinámicas, sin volver a subir el excel ni rehacer
 * bronze/silver. Esto es lo que hace demostrable "edito una regla
 * dinámica y re-audito un job existente sin resubir nada".
 */
export async function runGoldOnly(
  uploadId: string,
  onStatus: (status: PipelineStatus) => void,
): Promise<boolean> {
  onStatus({ type: "running" })
  await api.audits.runGold(uploadId)

  const goldReady = await waitForLayer(uploadId, "gold", onStatus)
  onStatus({ type: goldReady ? "complete" : "timeoutGold" })
  return goldReady
}

export function downloadBlobToDisk(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
