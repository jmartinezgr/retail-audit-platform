import { api } from "@/lib/api"

/**
 * El status del upload no distingue "silver ya terminó" de "silver
 * todavía corriendo" (ambos se ven PROCESSING) - así que en vez de
 * adivinar con un timeout, esperamos a que la capa exista de verdad
 * consultando su endpoint hasta que responda 200.
 */
async function waitForLayer(
  uploadId: string,
  layer: "silver" | "gold",
  onStatus: (msg: string) => void,
  timeoutMs = 120_000,
  intervalMs = 800,
): Promise<boolean> {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      await api.audits.layerPreview(uploadId, layer)
      return true
    } catch {
      const elapsed = Math.round((Date.now() - start) / 1000)
      onStatus(`Esperando "${layer}"... (${elapsed}s)`)
      await new Promise((r) => setTimeout(r, intervalMs))
    }
  }
  return false
}

export async function runFullPipeline(
  uploadId: string,
  onStatus: (msg: string) => void,
): Promise<boolean> {
  onStatus("Disparando bronze + silver...")
  await api.audits.run(uploadId)

  const silverReady = await waitForLayer(uploadId, "silver", onStatus)
  if (!silverReady) {
    onStatus("Timeout esperando silver.")
    return false
  }

  onStatus("Silver listo. Disparando gold...")
  await api.audits.runGold(uploadId)

  const goldReady = await waitForLayer(uploadId, "gold", onStatus)
  onStatus(
    goldReady
      ? "Pipeline completo (bronze → silver → gold)."
      : "Timeout esperando gold.",
  )
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
