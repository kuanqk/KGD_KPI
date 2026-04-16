<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import client from '../api/client.js'
import UserAccount from '../components/UserAccount.vue'

const jobs    = ref([])
const loading = ref(false)
const error   = ref(null)
const submitting = ref(false)

const SOURCES = [
  { value: 'inis',    label: 'ИНИС' },
  { value: 'isna',    label: 'ИСНА' },
  { value: 'dgd',     label: 'Данные ДГД' },
  { value: 'appeals', label: 'Обжалования' },
]

const STATUS_LABEL = {
  pending: 'Ожидание',
  running: 'Выполняется',
  done:    'Завершено',
  failed:  'Ошибка',
  partial: 'Частично',
}

const STATUS_COLOR = {
  pending: '#9CA3AF',
  running: '#3B82F6',
  done:    '#27AE60',
  failed:  '#E74C3C',
  partial: '#F39C12',
}

const selectedSource = ref('inis')
const dateFrom = ref(new Date().getFullYear() + '-01-01')
const dateTo   = ref(new Date().toISOString().slice(0, 10))

// ── Polling ────────────────────────────────────────────────────────────────────
let pollTimer = null

function hasRunning() {
  return jobs.value.some(j => j.status === 'running' || j.status === 'pending')
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(fetchJobs, 3000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

// ── API ────────────────────────────────────────────────────────────────────────
async function fetchJobs() {
  if (loading.value) return
  try {
    const { data } = await client.get('/etl/jobs/')
    jobs.value = (data.results ?? data).sort((a, b) =>
      new Date(b.started_at ?? 0) - new Date(a.started_at ?? 0)
    )
    if (hasRunning()) startPolling()
    else stopPolling()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  }
}

async function startImport() {
  submitting.value = true
  error.value = null
  try {
    await client.post('/etl/jobs/', {
      source: selectedSource.value,
      params: { date_from: dateFrom.value, date_to: dateTo.value },
    })
    await fetchJobs()
    startPolling()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка запуска импорта'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  loading.value = true
  await fetchJobs()
  loading.value = false
  if (hasRunning()) startPolling()
})

onUnmounted(() => stopPolling())

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU')
}
</script>

<template>
  <div class="view-page">
    <header class="view-header view-header--with-account">
      <h1 class="view-title">Загрузка данных</h1>
      <UserAccount />
    </header>

    <!-- Launch form -->
    <section class="launch-card">
      <h2 class="card-title">Запустить импорт</h2>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Источник</label>
          <select v-model="selectedSource" class="form-select">
            <option v-for="s in SOURCES" :key="s.value" :value="s.value">{{ s.label }}</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">С</label>
          <input v-model="dateFrom" type="date" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">По</label>
          <input v-model="dateTo" type="date" class="form-input" />
        </div>
        <button class="btn-primary" :disabled="submitting" @click="startImport">
          {{ submitting ? 'Запуск…' : '▶ Запустить' }}
        </button>
      </div>
      <div v-if="error" class="alert-error">{{ error }}</div>
    </section>

    <!-- Jobs list -->
    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">История задач</h2>
        <button class="btn-refresh" @click="fetchJobs">↻ Обновить</button>
      </div>

      <div v-if="loading" class="view-loading">Загрузка…</div>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Источник</th>
              <th>Статус</th>
              <th>Запущен</th>
              <th>Завершён</th>
              <th>Всего</th>
              <th>Загружено</th>
              <th>Ошибок</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.id" :class="{ 'row-running': job.status === 'running' }">
              <td>{{ job.id }}</td>
              <td>{{ SOURCES.find(s => s.value === job.source)?.label ?? job.source }}</td>
              <td>
                <span class="status-badge" :style="{ background: STATUS_COLOR[job.status] + '22', color: STATUS_COLOR[job.status] }">
                  <span class="status-dot" :style="{ background: STATUS_COLOR[job.status] }"></span>
                  {{ STATUS_LABEL[job.status] ?? job.status }}
                  <span v-if="job.status === 'running'" class="spinner">⟳</span>
                </span>
              </td>
              <td class="nowrap">{{ fmtDate(job.started_at) }}</td>
              <td class="nowrap">{{ fmtDate(job.finished_at) }}</td>
              <td>{{ job.records_total ?? '—' }}</td>
              <td>{{ job.records_imported ?? '—' }}</td>
              <td :class="{ 'err-cell': job.rows_failed > 0 }">{{ job.rows_failed ?? '—' }}</td>
            </tr>
            <tr v-if="!jobs.length">
              <td colspan="8" class="empty-cell">Нет задач импорта</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.view-page { min-height: 100vh; background: var(--color-bg); display: flex; flex-direction: column; gap: 16px; padding-bottom: 24px; }

.view-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 14px 24px;
}
.view-title { font-size: 18px; font-weight: 700; color: var(--color-text); }

.view-header.view-header--with-account .view-title {
  flex: 1;
  min-width: 0;
}

.launch-card {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin: 0 24px;
  padding: 20px 24px;
}
.card-title { font-size: 15px; font-weight: 600; color: var(--color-primary); margin-bottom: 14px; }

.form-row { display: flex; align-items: flex-end; gap: 14px; flex-wrap: wrap; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.form-select, .form-input {
  padding: 7px 10px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  outline: none;
  background: var(--color-surface);
}
.form-select:focus, .form-input:focus { border-color: var(--color-primary); }

.btn-primary {
  padding: 8px 18px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity .2s;
  height: 36px;
}
.btn-primary:disabled { opacity: .6; cursor: default; }

.alert-error {
  margin-top: 12px;
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
  margin: 0 24px;
  overflow: hidden;
}
.panel-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-title { font-size: 15px; font-weight: 600; color: var(--color-primary); }
.btn-refresh {
  background: none;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  padding: 4px 12px;
  font-size: 13px;
  cursor: pointer;
  color: var(--color-text-secondary);
}
.btn-refresh:hover { border-color: var(--color-primary); color: var(--color-primary); }

.view-loading { padding: 32px; text-align: center; color: var(--color-text-secondary); }
.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
  background: var(--color-bg);
  padding: 8px 12px;
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
}
.data-table td { padding: 9px 12px; border-bottom: 1px solid var(--color-border); }
.nowrap { white-space: nowrap; }
.empty-cell { text-align: center; padding: 32px; color: var(--color-text-secondary); }
.err-cell { color: var(--color-danger); font-weight: 600; }
.row-running { background: #EFF6FF; }

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}
.status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }

.spinner { display: inline-block; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
