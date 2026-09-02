import {
  ArrowRight,
  Database,
  FileSpreadsheet,
  Layers,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

const CAPAS = [
  {
    nombre: "Bronze",
    descripcion: "El excel crudo tal cual llegó, sin tipar ni validar nada. Trazabilidad total.",
    icon: FileSpreadsheet,
  },
  {
    nombre: "Silver",
    descripcion:
      "Tipado y validación estructural (fechas, números, campos obligatorios). Ninguna fila se descarta.",
    icon: Layers,
  },
  {
    nombre: "Gold",
    descripcion:
      "15 reglas de negocio contra los catálogos: existencia, vigencias, márgenes, cuadre de totales.",
    icon: ShieldCheck,
  },
]

const STACK = [
  "FastAPI",
  "Polars",
  "Delta Lake",
  "DuckDB",
  "Postgres",
  "MinIO",
  "React",
  "TypeScript",
]

export function LandingPage() {
  return (
    <div className="min-h-svh bg-background">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <span className="font-semibold tracking-tight">AuditLake</span>
          <Button size="sm" variant="outline" asChild>
            <Link to="/app">Probar la demo</Link>
          </Button>
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl flex-col gap-20 px-4 py-8">
        <section className="flex flex-col items-center gap-6 text-center">
        <Badge variant="outline" className="gap-1.5">
          <Sparkles className="size-3" /> Proyecto de portafolio
        </Badge>
        <h1 className="max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
          Un motor de auditoría de datos, por capas
        </h1>
        <p className="text-muted-foreground max-w-xl text-lg">
          Sube un excel de ventas de una cadena de tiendas ficticia y mira cómo se audita
          automáticamente contra 15 reglas de negocio — bronze, silver y gold, estilo lakehouse.
        </p>
        <div className="flex gap-3">
          <Button size="lg" asChild>
            <Link to="/app">
              Probar la demo <ArrowRight />
            </Link>
          </Button>
        </div>
      </section>

      <section className="flex flex-col gap-6">
        <div className="text-center">
          <h2 className="text-2xl font-semibold">Cómo funciona</h2>
          <p className="text-muted-foreground mt-1">
            El mismo patrón de capas (medallion architecture) que se usa en pipelines de datos
            reales, aplicado a un dominio simple para poder mostrarlo de punta a punta.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {CAPAS.map((capa) => (
            <Card key={capa.nombre}>
              <CardHeader>
                <capa.icon className="text-primary size-6" />
                <CardTitle>{capa.nombre}</CardTitle>
                <CardDescription>{capa.descripcion}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-4 text-center">
        <Database className="text-primary mx-auto size-8" />
        <h2 className="text-2xl font-semibold">De dónde viene la idea</h2>
        <p className="text-muted-foreground mx-auto max-w-2xl">
          El diseño está inspirado en un motor de reglas real que procesaba y auditaba
          facturación de una EPS colombiana con Databricks: catálogos maestros, validación
          cruzada, y una capa de auditoría explicable. Acá el dominio es una cadena de tiendas
          ficticia — sin Spark ni datos reales — pero el patrón (capas, trazabilidad, reglas
          estáticas y dinámicas) es el mismo.
        </p>
      </section>

      <section className="flex flex-col items-center gap-4">
        <h2 className="text-muted-foreground text-sm font-medium tracking-wide uppercase">
          Stack
        </h2>
        <div className="flex flex-wrap justify-center gap-2">
          {STACK.map((s) => (
            <Badge key={s} variant="secondary">
              {s}
            </Badge>
          ))}
        </div>
      </section>

        <section className="flex flex-col items-center gap-4 text-center pb-8">
          <h2 className="text-2xl font-semibold">¿Listo para verlo funcionar?</h2>
          <Button size="lg" asChild>
            <Link to="/app">
              Generar datos y auditar <ArrowRight />
            </Link>
          </Button>
        </section>
      </div>
    </div>
  )
}
