// Catálogo estático de las 18 reglas de gold, para mostrar en la landing
// sin depender del backend (es contenido de marketing, no datos de una
// corrida real). Los nombres de regla quedan en español a propósito -
// son datos del dominio, igual que en el resto de la app (ver
// i18n/translations.ts). Debe mantenerse en sync con
// domain/rules/engine.py y docs/DATA_MODEL.md § Gold si cambia el motor.

import type { TranslationKey } from "@/i18n/translations"

export interface RuleCatalogEntry {
  nombre: string
  severidad: "ERROR" | "WARNING"
  tipo: "endogena" | "exogena"
  descKey: TranslationKey
}

export const REGLAS_CABECERA: RuleCatalogEntry[] = [
  { nombre: "sede_existe", severidad: "ERROR", tipo: "exogena", descKey: "rule.sedeExiste" },
  { nombre: "sede_activa", severidad: "ERROR", tipo: "exogena", descKey: "rule.sedeActiva" },
  { nombre: "trabajador_existe", severidad: "ERROR", tipo: "exogena", descKey: "rule.trabajadorExiste" },
  { nombre: "trabajador_activo", severidad: "ERROR", tipo: "exogena", descKey: "rule.trabajadorActivo" },
  { nombre: "trabajador_pertenece_a_sede", severidad: "ERROR", tipo: "exogena", descKey: "rule.trabajadorPerteneceASede" },
  { nombre: "comprador_existe", severidad: "WARNING", tipo: "exogena", descKey: "rule.compradorExiste" },
  { nombre: "fecha_no_futura", severidad: "ERROR", tipo: "endogena", descKey: "rule.fechaNoFutura" },
  { nombre: "fecha_posterior_a_apertura", severidad: "ERROR", tipo: "exogena", descKey: "rule.fechaPosteriorAApertura" },
  { nombre: "factura_total_cuadra", severidad: "ERROR", tipo: "endogena", descKey: "rule.facturaTotalCuadra" },
]

export const REGLAS_ITEM: RuleCatalogEntry[] = [
  { nombre: "producto_existe", severidad: "ERROR", tipo: "exogena", descKey: "rule.productoExiste" },
  { nombre: "codigo_descuento_existe", severidad: "ERROR", tipo: "exogena", descKey: "rule.codigoDescuentoExiste" },
  { nombre: "codigo_descuento_vigente", severidad: "WARNING", tipo: "exogena", descKey: "rule.codigoDescuentoVigente" },
  { nombre: "codigo_descuento_aplica_a_sede", severidad: "WARNING", tipo: "exogena", descKey: "rule.codigoDescuentoAplicaASede" },
  { nombre: "codigo_descuento_aplica_a_categoria", severidad: "WARNING", tipo: "exogena", descKey: "rule.codigoDescuentoAplicaACategoria" },
  { nombre: "item_cuadra", severidad: "ERROR", tipo: "endogena", descKey: "rule.itemCuadra" },
  { nombre: "margen_no_negativo", severidad: "WARNING", tipo: "exogena", descKey: "rule.margenNoNegativo" },
  { nombre: "cantidad_dentro_de_transferencias", severidad: "WARNING", tipo: "exogena", descKey: "rule.cantidadDentroDeTransferencias" },
  { nombre: "item_duplicado_en_factura", severidad: "ERROR", tipo: "endogena", descKey: "rule.itemDuplicadoEnFactura" },
]
