import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from '@/api/client'

const AuthContext = createContext(null)

/** Monta a URL do Command Center a partir do hostname atual. */
function commandCenterUrl() {
  const port = import.meta.env.VITE_COMMAND_CENTER_PORT || '4001'
  return `${location.protocol}//${location.hostname}:${port}`
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem('fi_user')
    return raw ? JSON.parse(raw) : null
  })
  const [loading, setLoading] = useState(true)

  // Validate session on mount — suporta Bearer token OU cookie SSO (httpOnly).
  // O cookie portal_token é httpOnly, então document.cookie NÃO o enxerga.
  // Sempre chamamos /auth/me e deixamos o browser enviar o cookie automaticamente.
  useEffect(() => {
    api
      .get('/auth/me')
      .then((res) => {
        setUser(res.data)
        localStorage.setItem('fi_user', JSON.stringify(res.data))
      })
      .catch(() => {
        localStorage.removeItem('fi_token')
        localStorage.removeItem('fi_user')
        setUser(null)
        // Sem sessão válida → redireciona ao Command Center para login SSO
        window.location.href = commandCenterUrl()
      })
      .finally(() => setLoading(false))
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('fi_token')
    localStorage.removeItem('fi_user')
    setUser(null)
    // Redireciona ao Command Center no logout
    window.location.href = commandCenterUrl()
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
