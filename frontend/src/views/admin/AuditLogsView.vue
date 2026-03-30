<script setup>
import { ref, reactive } from 'vue'
import client from '../../api/client.js'

// ── Event config ───────────────────────────────────────────────────────────────
const EVENT_CONFIG = {
  import:       { label: 'Импорт',        icon: '↓', bg: '#DBEAFE', color: '#1D4ED8' },
  kpi_calc:     { label: 'Расчёт KPI',    icon: '⚙', bg: '#D1FAE5', color: '#065F46' },
  login:        { label: 'Вход',          icon: '→', bg: '#F3F4F6', color: '#374151' },
  logout:       { label: 'Выход',         icon: '←', bg: '#F3F4F6', color: '#374151' },
  export:       { label: 'Экспорт',       icon: '↑', bg: '#FEF3C7', color: '#92400E' },
  manual_input: { label: 'Ручной ввод',   icon: '✎', bg: '#EDE9FE', color: '#6D28D9' },
  correction:   { label: 'Корректировка', icon: '✱', bg: '#FEE2E2', color: '#991B1B' },
  formula_change:{ label: 'Формула',      icon: '∫', bg: '#FDF4FF', color: '#7C3AED' },
  approval:     { label: 'Утверждение',   icon: '✓', bg: '#D1FAE5', color: '#065F46' },
  user_mgmt:    { label: 'Пользователь',  icon: '👤', bg: '#F0F9FF', color: '#0369A1' },
}

const EVENT_OPTIONS = [
  { value: '', label: 'Все события' },
  ...Object.entries(EVENT_CONFIG).map(([value, cfg]) => ({ value, label: cfg.label })),
]

// ── State ──────────────────────────────────────────────────────────────────────
const logs     = ref([])
const loading  = ref(false)
const error    = ref(null)
const hasMore  = ref(false)
const cursor   = ref(null)

// Expanded details map: { [id]: true }
const expanded = ref({})

const filters = reactive({
  action:     '',
  user:       '',
  date_from:  '',
  date_to:    '',
})

// ── Load ───────────────────────────────────────────────────────────────────────
async function fetchLogs(append = false) {
  loading.value = true
  error.value = null
  try {
    const params = {
      action:    filters.action   || undefined,
      user:      filters.user     || undefined,
      date_from: filters.date_from || undefined,
      date_to:   filters.date_to   || undefined,
    }
    if (append && cursor.value) params.cursor = cursor.value

    const { data } = await client.get('/admin/audit-logs/', { params })

    const results = data.results ?? data
    logs.value = append ? [...logs.value, ...results] : results

    // Extract cursor from next URL
    if (data.next) {
      try { cursor.value = new URL(data.next).searchParams.get('cursor') }
      catch { cursor.value = null }
    } else {
      cursor.value = null
    }
    hasMore.value = !!data.next
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  cursor.value = null
  fetchLogs(false)
}

function loadMore() {
  fetchLogs(true)
}

fetchLogs()

// ── Helpers ────────────────────────────────────────────────────────────────────
function eventCfg(action) {
  return EVENT_CONFIG[action] ?? { label: action, icon: '•', bg: '#F3F4F6', color: '#374151' }
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU')
}

function fmtDetails(extra) {
  if (!extra || (typeof extra === 'object' && !Object.keys(extra).length)) return null
  return JSON.stringify(extra, null, 2)
}

function toggleExpand(id) {
  expanded.value = { ...expanded.value, [id]: !expanded.value[id] }
}
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <h1 class="view-title">Журнал действий</h1>
    </header>

    <!-- Filters -->
    <section class="filters-bar">
      <div class="filter-group">
        <label class="filter-label">Событие</label>
        <select v-model="filters.action" class="filter-select" @change="applyFilters">
          <option v-for="o in EVENT_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">Пользователь</label>
        <input
          v-model="filters.user"
          type="text"
          class="filter-input"
          placeholder="логин или имя"
          @keydown.enter="applyFilters"
        />
      </div>
      <div class="filter-group">
        <label class="filter-label">С</label>
        <input v-model="filters.date_from" type="date" class="filter-input" @change="applyFilters" />
      </div>
      <div class="filter-group">
        <label class="filter-label">По</label>
        <input v-model="filters.date_to" type="date" class="filter-input" @change="applyFilters" />
      </div>
      <button class="btn-apply" @click="applyFilters">Применить</button>
    </section>

    <div v-if="error" class="alert-error">{{ error }}</div>

    <!-- Table -->
    <section class="panel">
      <div v-if="loading && !logs.length" class="view-loading">Загрузка…</div>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th class="col-date">Дата / Время</th>
              <th class="col-user">Пользователь</th>
              <th class="col-event">Событие</th>
              <th class="col-ip">IP</th>
              <th class="col-details">Детали</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="log in logs" :key="log.id">
              <tr class="log-row" :class="{ 'row-expanded': expanded[log.id] }">
                <td class="td-date">{{ fmtDate(log.created_at) }}</td>
                <td class="td-user">
                  <span class="username">{{ log.user_display ?? log.user ?? '—' }}</span>
                </td>
                <td>
                  <span
                    class="event-badge"
                    :style="{ background: eventCfg(log.action).bg, color: eventCfg(log.action).color }"
                  >
                    <span class="event-icon">{{ eventCfg(log.action).icon }}</span>
                    {{ eventCfg(log.action).label }}
                  </span>
                </td>
                <td class="td-ip">{{ log.ip_address ?? '—' }}</td>
                <td class="td-details">
                  <button
                    v-if="fmtDetails(log.extra ?? log.details)"
                    class="btn-expand"
                    :class="{ active: expanded[log.id] }"
                    @click="toggleExpand(log.id)"
                  >
                    {{ expanded[log.id] ? '▲ Скрыть' : '▼ Детали' }}
                  </button>
                  <span v-else class="no-details">—</span>
                </td>
              </tr>
              <!-- Expanded details row -->
              <tr v-if="expanded[log.id]" class="details-row">
                <td colspan="5">
                  <pre class="details-json">{{ fmtDetails(log.extra ?? log.details) }}</pre>
                </td>
              </tr>
            </template>

            <tr v-if="!loading && !logs.length">
              <td colspan="5" class="empty-cell">Записей не найдено</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Load more -->
      <div class="load-more-bar">
        <div v-if="loading && logs.length" class="loading-inline">Загрузка…</div>
        <button v-else-if="hasMore" class="btn-load-more" @click="loadMore">
          Загрузить ещё
        </button>
        <span v-else-if="logs.length" class="end-mark">Все записи загружены</span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.view-page { min-height: 100vh; background: var(--color-bg); display: flex; flex-direction: column; gap: 0; }

.view-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 14px 24px;
}
.view-title { font-size: 18px; font-weight: 700; color: var(--color-text); }

.filters-bar {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 10px 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.filter-group { display: flex; align-items: center; gap: 6px; }
.filter-label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); white-space: nowrap; }
.filter-select, .filter-input {
  padding: 5px 8px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  background: var(--color-surface);
  outline: none;
}
.filter-select:focus, .filter-input:focus { border-color: var(--color-primary); }
.filter-input { width: 160px; }

.btn-apply {
  padding: 5px 14px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}

.alert-error {
  margin: 10px 24px;
  padding: 8px 12px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  font-size: 13px;
}

.panel {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin: 14px 24px 24px;
  overflow: hidden;
}
.view-loading { padding: 40px; text-align: center; color: var(--color-text-secondary); }
.table-wrap { overflow-x: auto; max-height: calc(100vh - 220px); overflow-y: auto; }

.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th {
  background: var(--color-bg);
  padding: 8px 12px;
  text-align: left;
  font-weight: 600;
  font-size: 11px;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 1;
  white-space: nowrap;
}
.col-date    { width: 150px; }
.col-user    { width: 160px; }
.col-event   { width: 140px; }
.col-ip      { width: 120px; }
.col-details { }

.data-table td { padding: 8px 12px; border-bottom: 1px solid var(--color-border); vertical-align: top; }

.log-row { transition: background .1s; }
.log-row:hover { background: #F8FAFC; }
.row-expanded { background: #F0F7FF; }

.td-date { white-space: nowrap; color: var(--color-text-secondary); font-size: 11px; }
.username { font-family: monospace; font-size: 12px; }
.td-ip { font-family: monospace; font-size: 11px; color: var(--color-text-secondary); }

.event-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.event-icon { font-size: 12px; }

.btn-expand {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: all .12s;
}
.btn-expand.active, .btn-expand:hover { border-color: var(--color-primary); color: var(--color-primary); }
.no-details { color: var(--color-border); }

.details-row td { background: #F8FAFC; padding: 0; }
.details-json {
  margin: 0;
  padding: 10px 16px;
  font-size: 11px;
  font-family: monospace;
  color: var(--color-text);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}

.empty-cell { text-align: center; padding: 32px; color: var(--color-text-secondary); }

.load-more-bar {
  padding: 12px;
  text-align: center;
  border-top: 1px solid var(--color-border);
}
.btn-load-more {
  padding: 7px 24px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 13px;
  cursor: pointer;
}
.loading-inline { font-size: 13px; color: var(--color-text-secondary); }
.end-mark { font-size: 12px; color: var(--color-text-secondary); }
</style>
