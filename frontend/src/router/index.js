import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

// Lazy-loaded views
const LoginView        = () => import('../views/LoginView.vue')
const DashboardView    = () => import('../views/DashboardView.vue')
const KPIDetailView    = () => import('../views/KPIDetailView.vue')
const CompareView      = () => import('../views/CompareView.vue')
const ImportView       = () => import('../views/ImportView.vue')
const DataEditorView   = () => import('../views/DataEditorView.vue')
const FormulasView     = () => import('../views/FormulasView.vue')
const CalculateView    = () => import('../views/CalculateView.vue')
const ApprovalView     = () => import('../views/ApprovalView.vue')
const HistoryView      = () => import('../views/HistoryView.vue')
const ManualInputView  = () => import('../views/ManualInputView.vue')
const UsersView        = () => import('../views/admin/UsersView.vue')
const AuditLogsView    = () => import('../views/admin/AuditLogsView.vue')
const ETLMonitorView   = () => import('../views/admin/ETLMonitorView.vue')

const routes = [
  // ── Публичные ───────────────────────────────────────────────────────────
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { public: true },
  },

  // ── Все аутентифицированные роли ────────────────────────────────────────
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: DashboardView,
    meta: { roles: ['admin', 'operator', 'reviewer', 'viewer'] },
  },
  {
    path: '/kpi/:regionCode',
    name: 'kpi-detail',
    component: KPIDetailView,
    meta: { roles: ['admin', 'operator', 'reviewer', 'viewer'] },
  },
  {
    path: '/compare',
    name: 'compare',
    component: CompareView,
    meta: { roles: ['admin', 'operator', 'reviewer', 'viewer'] },
  },
  {
    path: '/history',
    name: 'history',
    component: HistoryView,
    meta: { roles: ['admin', 'operator', 'reviewer', 'viewer'] },
  },

  // ── Оператор ────────────────────────────────────────────────────────────
  {
    path: '/import',
    name: 'import',
    component: ImportView,
    meta: { roles: ['operator', 'admin'] },
  },
  {
    path: '/data',
    name: 'data',
    component: DataEditorView,
    meta: { roles: ['operator', 'admin'] },
  },
  {
    path: '/formulas',
    name: 'formulas',
    component: FormulasView,
    meta: { roles: ['operator', 'admin'] },
  },
  {
    path: '/calculate',
    name: 'calculate',
    component: CalculateView,
    meta: { roles: ['operator', 'admin'] },
  },
  {
    path: '/manual-input',
    name: 'manual-input',
    component: ManualInputView,
    meta: { roles: ['operator', 'admin'] },
  },

  // ── Проверяющий ─────────────────────────────────────────────────────────
  {
    path: '/approve',
    name: 'approve',
    component: ApprovalView,
    meta: { roles: ['reviewer', 'admin'] },
  },

  // ── Администратор ───────────────────────────────────────────────────────
  {
    path: '/admin/users',
    name: 'admin-users',
    component: UsersView,
    meta: { roles: ['admin'] },
  },
  {
    path: '/admin/logs',
    name: 'admin-logs',
    component: AuditLogsView,
    meta: { roles: ['admin'] },
  },
  {
    path: '/admin/etl',
    name: 'admin-etl',
    component: ETLMonitorView,
    meta: { roles: ['admin'] },
  },

  // ── Fallback ─────────────────────────────────────────────────────────────
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ── Navigation guard ─────────────────────────────────────────────────────────

router.beforeEach(to => {
  const auth = useAuthStore()

  // Публичные маршруты (только /login) — пропускаем
  if (to.meta.public) {
    // Если уже залогинен — переправляем на dashboard
    if (auth.isAuthenticated) return { name: 'dashboard' }
    return true
  }

  // Не аутентифицирован → /login
  if (!auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // Проверяем роль (meta.roles определён и роль пользователя не в списке)
  const allowedRoles = to.meta.roles
  if (allowedRoles && auth.userRole && !allowedRoles.includes(auth.userRole)) {
    return { name: 'dashboard' }
  }

  return true
})

export default router
