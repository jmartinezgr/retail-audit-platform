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

export interface SheetPreview {
  row_count: number
  columns: string[]
  preview: Record<string, unknown>[]
}

/** bronze/silver - 2 hojas (facturas + items), no una tabla plana */
export interface DualLayerPreviewResponse {
  upload_id: string
  sheets: {
    facturas: SheetPreview
    items: SheetPreview
  }
}

/** gold - una sola tabla plana (preview fijo, primeras filas) */
export interface LayerPreviewResponse {
  upload_id: string
  row_count: number
  columns: string[]
  preview: Record<string, unknown>[]
}

export interface GoldRow {
  numero_factura: string
  item_id: number | null
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

export interface GoldMatrixRow {
  numero_factura: string
  regla: string
  severidad: "ERROR" | "WARNING"
  paso: boolean | null
  sede_codigo: string
  fecha: string
}

/** Página de la matriz factura x regla (peor caso) - filas largas, el
 * frontend las pivotea a una tabla ancha */
export interface GoldMatrixResponse {
  upload_id: string
  total: number
  limit: number
  offset: number
  rows: GoldMatrixRow[]
}

export interface FacturaDetailResponse {
  upload_id: string
  numero_factura: string
  facturas: Record<string, unknown>[]
  items: Record<string, unknown>[]
  evaluaciones_cabecera: GoldRow[]
  evaluaciones_items: GoldRow[]
  gold_ready: boolean
}

export interface SheetValidationResponse {
  columnas_encontradas: string[]
  columnas_faltantes: string[]
  columnas_opcionales_presentes: string[]
  columnas_extra: string[]
  valido: boolean
}

export interface ColumnValidationResponse {
  upload_id: string
  facturas: SheetValidationResponse
  items: SheetValidationResponse
  valido: boolean
}

export interface RuleFailureBreakdown {
  regla: string
  severidad: "ERROR" | "WARNING"
  facturas_afectadas: number
}

export interface DashboardResponse {
  upload_id: string
  total_facturas: number
  facturas_validas: number
  facturas_con_error: number
  facturas_solo_warning: number
  facturas_con_items_duplicados: number
  facturas_con_total_no_cuadra: number
  valor_total_registrado: number
  valor_validado: number
  reglas: RuleFailureBreakdown[]
}

export interface ExportProblematicResponse {
  download_url: string
  facturas_problematicas: number
}

export interface GenerateExcelRequest {
  facturas: number
  error_rate: number
}

export interface GenerateExcelResponse {
  download_url: string
  facturas_totales: number
  items_totales: number
  facturas_con_error: number
  errores_por_tipo: Record<string, number>
}
