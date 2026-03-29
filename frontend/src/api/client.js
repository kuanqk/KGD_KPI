/**
 * Axios-клиент с JWT interceptors.
 *
 * Request interceptor: добавляет Authorization: Bearer <token> из localStorage.
 * Response interceptor: при 401 пытается обновить токен через /auth/token/refresh/,
 *   повторяет оригинальный запрос; при неудаче — разлогинивает и редиректит на /login.
 */
import axios from 'axios'

export const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// ── Request interceptor ──────────────────────────────────────────────────────

client.interceptors.request.use(config => {
  const token = localStorage.getItem('access')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor (auto-refresh) ─────────────────────────────────────

let isRefreshing = false
let pendingQueue = []   // [{resolve, reject}]

function processQueue(error, newToken = null) {
  pendingQueue.forEach(({ resolve, reject }) => {
    error ? reject(error) : resolve(newToken)
  })
  pendingQueue = []
}

client.interceptors.response.use(
  response => response,
  async error => {
    const original = error.config

    // Пропускаем повторный запрос или запрос обновления токена
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }

    if (isRefreshing) {
      // Ставим запрос в очередь до завершения обновления токена
      return new Promise((resolve, reject) => {
        pendingQueue.push({ resolve, reject })
      }).then(token => {
        original.headers.Authorization = `Bearer ${token}`
        return client(original)
      })
    }

    original._retry = true
    isRefreshing = true

    const refresh = localStorage.getItem('refresh')
    if (!refresh) {
      isRefreshing = false
      _redirectToLogin()
      return Promise.reject(error)
    }

    try {
      const { data } = await axios.post('/api/v1/auth/token/refresh/', { refresh })
      const newAccess = data.access
      localStorage.setItem('access', newAccess)
      if (data.refresh) localStorage.setItem('refresh', data.refresh)
      client.defaults.headers.common.Authorization = `Bearer ${newAccess}`
      processQueue(null, newAccess)
      original.headers.Authorization = `Bearer ${newAccess}`
      return client(original)
    } catch (refreshError) {
      processQueue(refreshError, null)
      _clearSession()
      _redirectToLogin()
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  },
)

function _clearSession() {
  localStorage.removeItem('access')
  localStorage.removeItem('refresh')
}

function _redirectToLogin() {
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

export default client
