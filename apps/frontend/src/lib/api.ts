import type {
  AvailableFieldsResponse,
  ColumnValidationResponse,
  DashboardResponse,
  DualLayerPreviewResponse,
  ExportProblematicResponse,
  FacturaDetailResponse,
  GenerateExcelRequest,
  GenerateExcelResponse,
  GoldMatrixResponse,
  GoldPageResponse,
  GoldSummaryResponse,
  LayerPreviewResponse,
  RequestUploadUrlResponse,
  RuleDefinition,
  RuleDefinitionInput,
  RunAuditResponse,
  UploadListResponse,
  UploadStatusResponse,
} from "@/types/api"
import { getSessionId } from "@/lib/session"

// Dev: el dev server de Vite reenvía /api -> el backend (ver vite.config.ts),
// no hace falta VITE_API_BASE_URL. Prod (Vercel): frontend y backend viven en
// dominios distintos, así que VITE_API_BASE_URL apunta directo al backend
// desplegado (ej. https://auditlake-backend.onrender.com).
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api"

class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

const GENERIC_ERROR_MESSAGE = "Something went wrong. Please try again."
const CONNECTION_ERROR_MESSAGE = "Couldn't reach the server. Please try again in a moment."

/** FastAPI's default error shape is {"detail": "..."} - use that if present,
 * it's usually already a readable sentence. Otherwise fall back to something
 * generic instead of surfacing raw status text/HTML to the user. */
async function readableErrorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data?.detail === "string" && data.detail.trim()) return data.detail
  } catch {
    // not JSON - ignore, fall through to generic message
  }
  return GENERIC_ERROR_MESSAGE
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** El free tier de Render a veces resetea una conexión concurrente mientras
 * el worker está ocupado procesando el pipeline (ver docs/PLANNING.md §9) -
 * eso se ve como un fallo de red o un 5xx, no como un error real. Solo
 * reintentamos GETs (idempotentes) para no disparar dos veces una mutación
 * (ej. correr el pipeline por duplicado). */
async function request<T>(path: string, init?: RequestInit, retries = 2): Promise<T> {
  const method = init?.method?.toUpperCase() ?? "GET"
  const canRetry = method === "GET"

  for (let attempt = 0; ; attempt++) {
    let res: Response
    try {
      res = await fetch(`${API_BASE}${path}`, {
        headers: {
          ...(init?.body ? { "Content-Type": "application/json" } : {}),
          "X-Client-Id": getSessionId(),
        },
        ...init,
      })
    } catch {
      if (canRetry && attempt < retries) {
        await sleep(500 * (attempt + 1))
        continue
      }
      throw new ApiError(0, CONNECTION_ERROR_MESSAGE)
    }

    if (!res.ok) {
      if (canRetry && res.status >= 500 && attempt < retries) {
        await sleep(500 * (attempt + 1))
        continue
      }
      throw new ApiError(res.status, await readableErrorMessage(res))
    }
    return res.json() as Promise<T>
  }
}

export const api = {
  uploads: {
    list: (limit = 50) =>
      request<UploadListResponse>(`/uploads/?limit=${limit}`),

    status: (uploadId: string) =>
      request<UploadStatusResponse>(`/uploads/${uploadId}/status`),

    requestUploadUrl: (filename: string) =>
      request<RequestUploadUrlResponse>("/uploads/request-upload-url", {
        method: "POST",
        body: JSON.stringify({ filename }),
      }),

    confirm: (uploadId: string) =>
      request<{ upload_id: string; status: string }>(
        `/uploads/confirm/${uploadId}`,
        { method: "POST" },
      ),

    validateColumns: (uploadId: string) =>
      request<ColumnValidationResponse>(`/uploads/${uploadId}/validate-columns`),
  },

  audits: {
    run: (uploadId: string) =>
      request<RunAuditResponse>(`/audits/${uploadId}/run`, {
        method: "POST",
      }),

    runGold: (uploadId: string) =>
      request<RunAuditResponse>(`/audits/${uploadId}/run-gold`, {
        method: "POST",
      }),

    dualLayerPreview: (uploadId: string, layer: "bronze" | "silver") =>
      request<DualLayerPreviewResponse>(`/audits/${uploadId}/${layer}`),

    goldPreview: (uploadId: string) =>
      request<LayerPreviewResponse>(`/audits/${uploadId}/gold`),

    goldSummary: (uploadId: string) =>
      request<GoldSummaryResponse>(`/audits/${uploadId}/gold/summary`),

    goldMatrix: (uploadId: string, limit: number, offset: number) =>
      request<GoldMatrixResponse>(
        `/audits/${uploadId}/gold/matrix?limit=${limit}&offset=${offset}`,
      ),

    queryGold: (
      uploadId: string,
      params: {
        limit: number
        offset: number
        severidad?: string
        regla?: string
        sedeCodigo?: string
        paso?: boolean
        numeroFactura?: string
      },
    ) => {
      const qs = new URLSearchParams()
      qs.set("limit", String(params.limit))
      qs.set("offset", String(params.offset))
      if (params.severidad) qs.set("severidad", params.severidad)
      if (params.regla) qs.set("regla", params.regla)
      if (params.sedeCodigo) qs.set("sede_codigo", params.sedeCodigo)
      if (params.paso !== undefined) qs.set("paso", String(params.paso))
      if (params.numeroFactura) qs.set("numero_factura", params.numeroFactura)
      return request<GoldPageResponse>(
        `/audits/${uploadId}/gold/query?${qs.toString()}`,
      )
    },

    facturaDetail: (uploadId: string, numeroFactura: string) =>
      request<FacturaDetailResponse>(
        `/audits/${uploadId}/factura/${encodeURIComponent(numeroFactura)}`,
      ),

    dashboard: (uploadId: string) =>
      request<DashboardResponse>(`/audits/${uploadId}/dashboard`),

    exportProblematic: (uploadId: string) =>
      request<ExportProblematicResponse>(`/audits/${uploadId}/export/problematic`, {
        method: "POST",
      }),
  },

  demo: {
    generateExcel: (payload: GenerateExcelRequest) =>
      request<GenerateExcelResponse>("/demo/generate-excel", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  rules: {
    list: () => request<RuleDefinition[]>("/rules/"),

    fields: () => request<AvailableFieldsResponse>("/rules/fields"),

    create: (payload: RuleDefinitionInput) =>
      request<RuleDefinition>("/rules/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    update: (id: number, payload: Partial<RuleDefinitionInput & { activa: boolean }>) =>
      request<RuleDefinition>(`/rules/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),

    remove: (id: number) =>
      request<{ deleted: boolean }>(`/rules/${id}`, { method: "DELETE" }),
  },
}

/** Sube un blob directo a la URL prefirmada de MinIO - no pasa por /api,
 * es una URL absoluta que el backend ya devolvió completa. */
export async function uploadToPresignedUrl(
  uploadUrl: string,
  blob: Blob,
): Promise<void> {
  const res = await fetch(uploadUrl, { method: "PUT", body: blob })
  if (!res.ok) {
    throw new ApiError(res.status, "Could not upload the file to storage")
  }
}

/** Flujo completo: pedir URL -> subir -> confirmar. Devuelve el upload_id. */
export async function uploadFile(
  blob: Blob,
  filename: string,
): Promise<string> {
  const { upload_url, upload_id } = await api.uploads.requestUploadUrl(filename)
  await uploadToPresignedUrl(upload_url, blob)
  await api.uploads.confirm(upload_id)
  return upload_id
}

export { ApiError }
