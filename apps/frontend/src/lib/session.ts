const STORAGE_KEY = "auditlake_session_id"

/**
 * ID anónimo por navegador, sin login - se genera una vez y se guarda en
 * localStorage. El backend lo usa (header X-Client-Id) para que la lista
 * de uploads de la demo pública no se mezcle entre visitantes.
 */
export function getSessionId(): string {
  try {
    let id = localStorage.getItem(STORAGE_KEY)
    if (!id) {
      id = crypto.randomUUID()
      localStorage.setItem(STORAGE_KEY, id)
    }
    return id
  } catch {
    // localStorage puede fallar (modo privado, storage bloqueado) - una
    // sesión de un solo request es mejor que romper la app.
    return crypto.randomUUID()
  }
}
