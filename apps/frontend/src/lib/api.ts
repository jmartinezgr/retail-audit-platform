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

// El dev server de Vite reenvía /api -> el backend (ver vite.config.ts).
// En prod, esto se vuelve la URL real del backend desplegado.
const API_BASE = "/api"

class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      "X-Client-Id": getSessionId(),
    },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new ApiError(res.status, text || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
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
