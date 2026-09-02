import path from "node:path"

import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // El backend no necesita CORS para el frontend real: el dev server
      // de Vite reenvía /api -> :8000 mismo-origen. En prod, el backend
      // desplegado sí necesita CORS acotado al dominio real (ver
      // CLAUDE.md sobre el CORS "*" provisional que NO se commiteó).
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
})
