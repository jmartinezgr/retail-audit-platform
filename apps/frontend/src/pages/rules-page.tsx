import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Loader2, Plus, Power, Trash2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useI18n } from "@/lib/i18n"
import { api } from "@/lib/api"
import type { AmbitoRegla, Operador, RuleDefinition, TipoReglaDinamica } from "@/types/api"

const OPERADORES: Operador[] = [">", ">=", "<", "<=", "==", "!="]

function emptyForm() {
  return {
    nombre: "",
    tipo: "UMBRAL" as TipoReglaDinamica,
    ambito: "ITEM" as AmbitoRegla,
    severidad: "WARNING" as "ERROR" | "WARNING",
    mensaje: "",
    campo: "",
    operador: ">" as Operador,
    valor: "",
    filtroCategoria: "__any__",
    filtroSede: "__any__",
    sedeCodigo: "",
    fechaInicio: "",
    fechaFin: "",
  }
}

function RuleRow({ rule, onToggle, onDelete }: {
  rule: RuleDefinition
  onToggle: (rule: RuleDefinition) => void
  onDelete: (rule: RuleDefinition) => void
}) {
  const { t } = useI18n()

  const resumen =
    rule.tipo === "UMBRAL"
      ? t("rules.summaryUmbral", { campo: rule.campo ?? "", operador: rule.operador ?? "", valor: rule.valor ?? "" })
      : t("rules.summaryVentana", { sede: rule.sede_codigo ?? "", inicio: rule.fecha_inicio ?? "", fin: rule.fecha_fin ?? "" })

  return (
    <div className={`flex flex-col gap-2 rounded-lg border px-4 py-3 sm:flex-row sm:items-center sm:justify-between ${!rule.activa ? "opacity-60" : ""}`}>
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm font-medium">{rule.nombre}</span>
          <Badge variant="outline" className="text-muted-foreground font-normal">{rule.tipo}</Badge>
          <Badge variant="outline" className="text-muted-foreground font-normal">{rule.ambito}</Badge>
          <Badge variant={rule.severidad === "ERROR" ? "destructive" : "outline"} className="font-normal">
            {rule.severidad}
          </Badge>
          {!rule.activa && <Badge variant="secondary">{t("rules.badgeInactive")}</Badge>}
        </div>
        <span className="text-muted-foreground font-mono text-xs">{resumen}</span>
        <span className="text-muted-foreground text-xs">{rule.mensaje}</span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => onToggle(rule)}>
          <Power className="size-3.5" /> {rule.activa ? t("rules.deactivate") : t("rules.activate")}
        </Button>
        <Button variant="outline" size="sm" onClick={() => onDelete(rule)}>
          <Trash2 className="size-3.5" /> {t("rules.delete")}
        </Button>
      </div>
    </div>
  )
}

export function RulesPage() {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const [form, setForm] = useState(emptyForm())
  const [creating, setCreating] = useState(false)

  const rulesQuery = useQuery({ queryKey: ["rules"], queryFn: () => api.rules.list() })
  const fieldsQuery = useQuery({ queryKey: ["rule-fields"], queryFn: () => api.rules.fields() })

  function update<K extends keyof ReturnType<typeof emptyForm>>(key: K, value: ReturnType<typeof emptyForm>[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleToggle(rule: RuleDefinition) {
    try {
      await api.rules.update(rule.id, { activa: !rule.activa })
      await queryClient.invalidateQueries({ queryKey: ["rules"] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : t("rules.toastUpdateError"))
    }
  }

  async function handleDelete(rule: RuleDefinition) {
    if (!window.confirm(t("rules.confirmDelete", { nombre: rule.nombre }))) return
    try {
      await api.rules.remove(rule.id)
      await queryClient.invalidateQueries({ queryKey: ["rules"] })
      toast.success(t("rules.toastDeleted"))
    } catch (e) {
      toast.error(e instanceof Error ? e.message : t("rules.toastDeleteError"))
    }
  }

  async function handleCreate() {
    setCreating(true)
    try {
      const base = {
        nombre: form.nombre.trim(),
        tipo: form.tipo,
        severidad: form.severidad,
        mensaje: form.mensaje.trim(),
      }
      const payload =
        form.tipo === "UMBRAL"
          ? {
              ...base,
              ambito: form.ambito,
              campo: form.campo,
              operador: form.operador,
              valor: Number(form.valor),
              filtro_categoria: form.ambito === "ITEM" && form.filtroCategoria !== "__any__" ? form.filtroCategoria : null,
              filtro_sede: form.filtroSede !== "__any__" ? form.filtroSede : null,
              sede_codigo: null,
              fecha_inicio: null,
              fecha_fin: null,
            }
          : {
              ...base,
              ambito: "CABECERA" as AmbitoRegla,
              campo: null,
              operador: null,
              valor: null,
              filtro_categoria: null,
              filtro_sede: null,
              sede_codigo: form.sedeCodigo,
              fecha_inicio: form.fechaInicio,
              fecha_fin: form.fechaFin,
            }

      const created = await api.rules.create(payload)
      await queryClient.invalidateQueries({ queryKey: ["rules"] })
      toast.success(t("rules.toastCreated", { nombre: created.nombre }))
      setForm(emptyForm())
    } catch (e) {
      toast.error(e instanceof Error ? e.message : t("rules.toastCreateError"))
    } finally {
      setCreating(false)
    }
  }

  const campoOptions = form.ambito === "CABECERA" ? fieldsQuery.data?.cabecera : fieldsQuery.data?.item
  const canCreate =
    form.nombre.trim() &&
    form.mensaje.trim() &&
    (form.tipo === "UMBRAL"
      ? form.campo && form.operador && form.valor !== ""
      : form.sedeCodigo && form.fechaInicio && form.fechaFin)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">{t("rules.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("rules.subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("rules.existingTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {rulesQuery.isLoading && <p className="text-muted-foreground text-sm">{t("rules.loading")}</p>}
          {rulesQuery.data?.length === 0 && <p className="text-muted-foreground text-sm">{t("rules.noRules")}</p>}
          {rulesQuery.data?.map((rule) => (
            <RuleRow key={rule.id} rule={rule} onToggle={handleToggle} onDelete={handleDelete} />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Plus className="size-4" /> {t("rules.newTitle")}
          </CardTitle>
          <CardDescription>{t("rules.fieldNombreHint")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label>{t("rules.fieldNombre")}</Label>
              <Input value={form.nombre} onChange={(e) => update("nombre", e.target.value)} placeholder="descuento_maximo_ropa" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>{t("rules.fieldTipo")}</Label>
              <Select value={form.tipo} onValueChange={(v) => update("tipo", v as TipoReglaDinamica)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="UMBRAL">{t("rules.tipoUmbral")}</SelectItem>
                  <SelectItem value="VENTANA_EXCLUSION">{t("rules.tipoVentana")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {form.tipo === "UMBRAL" ? (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="flex flex-col gap-1.5">
                  <Label>{t("rules.fieldAmbito")}</Label>
                  <Select value={form.ambito} onValueChange={(v) => update("ambito", v as AmbitoRegla)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="CABECERA">{t("rules.ambitoCabecera")}</SelectItem>
                      <SelectItem value="ITEM">{t("rules.ambitoItem")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>{t("rules.fieldCampo")}</Label>
                  <Select value={form.campo} onValueChange={(v) => update("campo", v)}>
                    <SelectTrigger><SelectValue placeholder={t("rules.fieldCampoPlaceholder")} /></SelectTrigger>
                    <SelectContent>
                      {campoOptions?.map((c) => (
                        <SelectItem key={c.campo} value={c.campo}>{c.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>{t("rules.fieldOperador")}</Label>
                  <Select value={form.operador} onValueChange={(v) => update("operador", v as Operador)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {OPERADORES.map((op) => (
                        <SelectItem key={op} value={op}>{op}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="flex flex-col gap-1.5">
                  <Label>{t("rules.fieldValor")}</Label>
                  <Input type="number" step="any" value={form.valor} onChange={(e) => update("valor", e.target.value)} />
                </div>
                {form.ambito === "ITEM" && (
                  <div className="flex flex-col gap-1.5">
                    <Label>{t("rules.fieldFiltroCategoria")}</Label>
                    <Select value={form.filtroCategoria} onValueChange={(v) => update("filtroCategoria", v)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__any__">{t("rules.anyCategoria")}</SelectItem>
                        {fieldsQuery.data?.categorias.map((c) => (
                          <SelectItem key={c} value={c}>{c}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <div className="flex flex-col gap-1.5">
                  <Label>{t("rules.fieldFiltroSede")}</Label>
                  <Select value={form.filtroSede} onValueChange={(v) => update("filtroSede", v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__any__">{t("rules.anySede")}</SelectItem>
                      {fieldsQuery.data?.sedes.map((s) => (
                        <SelectItem key={s} value={s}>{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </>
          ) : (
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="flex flex-col gap-1.5">
                <Label>{t("rules.fieldSede")}</Label>
                <Select value={form.sedeCodigo} onValueChange={(v) => update("sedeCodigo", v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {fieldsQuery.data?.sedes.map((s) => (
                      <SelectItem key={s} value={s}>{s}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>{t("rules.fieldFechaInicio")}</Label>
                <Input type="date" value={form.fechaInicio} onChange={(e) => update("fechaInicio", e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>{t("rules.fieldFechaFin")}</Label>
                <Input type="date" value={form.fechaFin} onChange={(e) => update("fechaFin", e.target.value)} />
              </div>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label>{t("rules.fieldSeveridad")}</Label>
              <Select value={form.severidad} onValueChange={(v) => update("severidad", v as "ERROR" | "WARNING")}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ERROR">ERROR</SelectItem>
                  <SelectItem value="WARNING">WARNING</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>{t("rules.fieldMensaje")}</Label>
              <Input value={form.mensaje} onChange={(e) => update("mensaje", e.target.value)} />
            </div>
          </div>

          <Button onClick={handleCreate} disabled={!canCreate || creating} className="w-fit">
            {creating ? <Loader2 className="animate-spin" /> : <Plus />}
            {t("rules.createButton")}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
