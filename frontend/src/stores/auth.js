import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import client from '../api/client.js'

export const useAuthStore = defineStore('auth', () => {
  // ── State ──────────────────────────────────────────────────────────────────
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access') || null)
  const refreshToken = ref(localStorage.getItem('refresh') || null)
  const loading = ref(false)
  const error = ref(null)

  // ── Getters ────────────────────────────────────────────────────────────────
  const isAuthenticated = computed(() => !!accessToken.value)
  const userRole = computed(() => user.value?.role ?? null)
  const isAdmin = computed(() => userRole.value === 'admin')
  const isOperator = computed(() => userRole.value === 'operator')
  const isReviewer = computed(() => userRole.value === 'reviewer')
  const isViewer = computed(() => userRole.value === 'viewer')
  const canSeeAllRegions = computed(() =>
    ['admin', 'operator', 'reviewer'].includes(userRole.value),
  )

  // ── Actions ────────────────────────────────────────────────────────────────

  async function login(username, password) {
    loading.value = true
    error.value = null
    try {
      const { data } = await client.post('/auth/login/', { username, password })
      accessToken.value = data.access
      refreshToken.value = data.refresh
      localStorage.setItem('access', data.access)
      localStorage.setItem('refresh', data.refresh)
      await fetchCurrentUser()
    } catch (err) {
      error.value =
        err.response?.data?.detail ?? 'Неверное имя пользователя или пароль.'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await client.post('/auth/logout/')
    } catch {
      // игнорируем ошибки сети при выходе
    } finally {
      _clearSession()
    }
  }

  async function fetchCurrentUser() {
    if (!accessToken.value) return
    try {
      // Используем UserViewSet — admin/users/me не существует, поэтому
      // пробуем получить текущего пользователя через токен (декодируем user_id
      // или используем отдельный endpoint). Пока используем /admin/users/
      // с id из JWT payload (base64 decode).
      const payload = _decodeJwt(accessToken.value)
      if (!payload?.user_id) return
      const { data } = await client.get(`/admin/users/${payload.user_id}/`)
      user.value = data
    } catch {
      // Если нет доступа к /admin/users/ (не admin) — оставляем user как null.
      // Роль будет недоступна до реализации /api/v1/auth/me/ в следующем спринте.
    }
  }

  function _clearSession() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    localStorage.removeItem('access')
    localStorage.removeItem('refresh')
  }

  function _decodeJwt(token) {
    try {
      const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
      return JSON.parse(atob(base64))
    } catch {
      return null
    }
  }

  // Восстанавливаем пользователя при старте, если есть токен
  if (accessToken.value) {
    fetchCurrentUser()
  }

  return {
    user,
    accessToken,
    refreshToken,
    loading,
    error,
    isAuthenticated,
    userRole,
    isAdmin,
    isOperator,
    isReviewer,
    isViewer,
    canSeeAllRegions,
    login,
    logout,
    fetchCurrentUser,
  }
})
