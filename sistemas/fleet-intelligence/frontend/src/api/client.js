import axios from 'axios'

const baseURL = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({
  baseURL,
  timeout: 15000,
  withCredentials: true, // Envia cookies (portal_token SSO) em requests cross-origin
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('fi_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    // 401 handler — limpa tokens locais e propaga o erro.
    // O redirect ao Command Center é feito pelo AuthContext (centralmente),
    // não aqui, para evitar race conditions no mount inicial.
    if (err.response?.status === 401) {
      localStorage.removeItem('fi_token')
      localStorage.removeItem('fi_user')
    }
    return Promise.reject(err)
  },
)

/** Extract a human-readable error message from axios error. */
export function errMsg(err, fallback = 'Algo deu errado') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
  return err?.message || fallback
}
