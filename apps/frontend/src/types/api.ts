// Mirrors apps/backend/src/api/*/schemas.py - a la mano hasta que valga
// la pena generarlos con openapi-typescript.

export type UploadStatus =
  | "REQUESTED"
  | "UPLOADED"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED"

export interface RequestUploadUrlResponse {
  upload_url: string
  object_name: string
  upload_id: string
}

export interface UploadStatusResponse {
  upload_id: string
  filename: string
  status: UploadStatus
  created_at: string
}

export interface UploadListResponse {
  count: number
  uploads: UploadStatusResponse[]
}

export interface RunAuditResponse {
  upload_id: string
  status: string
}

export interface LayerPreviewResponse {
  upload_id: string
  row_count: number
  columns: string[]
  preview: Record<string, unknown>[]
}

export interface GoldRow {
  numero_factura: string
  sede_codigo: string
  fecha: string
  regla: string
  severidad: "ERROR" | "WARNING"
  paso: boolean | null
  mensaje: string
}

export interface GoldPageResponse {
  upload_id: string
  total: number
  limit: number
  offset: number
  rows: GoldRow[]
}

export interface GoldSummaryRow {
  regla: string
  severidad: "ERROR" | "WARNING"
  paso: boolean | null
  n: number
}

export interface GoldSummaryResponse {
  upload_id: string
  counts: GoldSummaryRow[]
}

export interface ColumnValidationResponse {
  upload_id: string
  columnas_encontradas: string[]
  columnas_faltantes: string[]
  columnas_opcionales_presentes: string[]
  columnas_extra: string[]
  valido: boolean
}

export interface GenerateExcelRequest {
  filas: number
  error_rate: number
}

export interface GenerateExcelResponse {
  download_url: string
  filas_totales: number
  filas_con_error: number
  errores_por_tipo: Record<string, number>
}
