import { Link, Outlet } from "react-router-dom"

export function AppLayout() {
  return (
    <div className="min-h-svh bg-background">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3">
          <Link to="/app" className="font-semibold tracking-tight">
            AuditLake
          </Link>
          <span className="text-muted-foreground text-sm">
            motor de auditoría de datos por capas
          </span>
          <Link to="/" className="text-muted-foreground ml-auto text-sm hover:underline">
            Sobre el proyecto
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
