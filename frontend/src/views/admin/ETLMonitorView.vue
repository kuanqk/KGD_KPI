<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import client from '../../api/client.js'

// ── State ──────────────────────────────────────────────────────────────────────
const jobs     = ref([])
const loading  = ref(true)
const error    = ref(null)
const errorModal = ref(null)   // { job } — show error_message popup

let autoTimer = null

// ── Status config ──────────────────────────────────────────────────────────────
const STATUS = {
  pending: { label: 'Ожидание',    color: '#9CA3AF', bg: '#F3F4F6', animate: false },
  running: { label: 'Выполняется', color: '#2563EB', bg: '#DBEAFE', animate: true  },
  done:    { label: 'Завершено',   color: '#16A34A', bg: '#D1FAE5', animate: false },
  failed:  { label: 'Ошибка',      color: '#DC2626', bg: '#FEE2E2', animate: false },
  partial: { label: 'Частично',    color: '#D97706', bg: '#FEF3C7', animate: false },
}

const SOURCES = {
  inis:    'ИНИС',
  isna:    'ИСНА',
  dgd:     'Данные ДГД',
  appeals: 'Обжалования',
}

// ── Stats ──────────────────────────────────────────────────────────────────────
const stats = computed(() => ({
  total:   jobs.value.length,
  done:    jobs.value.filter(j => j.status === 'done').length,
  failed:  jobs.value.filter(j => j.status === 'failed' || j.status === 'partial').length,
  running: jobs.value.filter(j => j.status === 'running' || j.status === 'pending').length,
}))

const hasRunning = computed(() =>
  jobs.value.some(j => j.status === 'running' || j.status === 'pending')
)

// ── Auto-refresh ───────────────────────────────────────────────────────────────
function startAutoRefresh() {
  if (autoTimer) return
  autoTimer = setInterval(async () => {
    if (hasRunning.value) await fetchJobs(true)
    else stopAutoRefresh()
  }, 10_000)
}

function stopAutoRefresh() {
  if (autoTimer) { clearInterval(autoTimer); autoTimer = null }
}

// ── Fetch ──────────────────────────────────────────────────────────────────────
async function fetchJobs(silent = false) {
  if (!silent) loading.value = true
  error.value = null
  try {
    const { data } = await client.get('/etl/jobs/')
    jobs.value = (data.results ?? data).sort(
      (a, b) => new Date(b.started_at ?? 0) - new Date(a.started_at ?? 0)
    )
    if (hasRunning.value) startAutoRefresh()
    else stopAutoRefresh()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

onMounted(() => fetchJobs())
onUnmounted(() => stopAutoRefresh())

// ── Helpers ───────────────────────────────────────────────────────────────────
function statusCfg(status) {
  return STATUS[status] ?? STATUS.pending
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU')
}

function duration(start, end) {
  if (!start || !end) return '—'
  const ms = new Date(end) - new Date(start)
  if (ms < 1000) return ms + 'мс'
  if (ms < 60000) return (ms / 1000).toFixed(1) + 'с'
  return Math.round(ms / 60000) + 'мин'
}

function progress(job) {
  if (!job.records_total || job.records_total === 0) return null
  return Math.round((job.records_imported / job.records_total) * 100)
}
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <h1 class="view-title">Мониторинг ETL</h1>
      <div class="header-right">
        <span v-if="hasRunning" class="auto-badge">⟳ Авто-обновление 10с</span>
        <button class="btn-refresh" @click="fetchJobs()">↻ Обновить</button>
      </div>
    </header>

    <div v-if="error" class="alert-error">{{ error }}</div>

    <!-- Stats cards -->
    <section class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{{ stats.total }}</span>
        <span class="stat-label">Всего импортов</span>
      </div>
      <div class="stat-card stat-success">
        <span class="stat-value">{{ stats.done }}</span>
        <span class="stat-label">Успешных</span>
      </div>
      <div class="stat-card stat-danger">
        <span class="stat-value">{{ stats.failed }}</span>
        <span class="stat-label">С ошибками</span>
      </div>
      <div class="stat-card stat-running">
        <span class="stat-value">{{ stats.running }}</span>
        <span class="stat-label">В процессе</span>
      </div>
    </section>

    <!-- Jobs table -->
    <section class="panel">
      <div v-if="loading" class="view-loading">Загрузка…</div>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Источник</th>
              <th>Статус</th>
              <th class="th-center">Прогресс</th>
              <th class="th-right">Загружено</th>
              <th class="th-right">Всего</th>
              <th class="th-right">Ошибок</th>
              <th>Начало</th>
              <th>Конец</th>
              <th>Длит.</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="job in jobs"
              :key="job.id"
              class="job-row"
              :class="{ 'row-running': job.status === 'running' }"
            >
              <td class="td-id">{{ job.id }}</td>
              <td>
                <span class="source-badge">{{ SOURCES[job.source] ?? job.source }}</span>
              </td>
              <td>
                <span
                  class="status-badge"
                  :style="{
                    background: statusCfg(job.status).bg,
                    color: statusCfg(job.status).color,
                  }"
                >
                  <span
                    class="status-dot"
                    :style="{ background: statusCfg(job.status).color }"
                    :class="{ 'dot-pulse': statusCfg(job.status).animate }"
                  ></span>
                  {{ statusCfg(job.status).label }}
                </span>
                <!-- Error button -->
                <button
                  v-if="job.status === 'failed' && job.error_message"
                  class="btn-err"
                  title="Показать ошибку"
                  @click="errorModal = job"
                >⚠</button>
              </td>

              <!-- Progress bar -->
              <td class="td-center td-progress">
                <div v-if="progress(job) != null" class="progress-wrap">
                  <div
                    class="progress-bar"
                    :class="job.status === 'failed' ? 'bar-error' : 'bar-ok'"
                    :style="{ width: progress(job) + '%' }"
                  ></div>
                  <span class="progress-label">{{ progress(job) }}%</span>
                </div>
                <span v-else class="muted">—</span>
              </td>

              <td class="td-right">{{ job.records_imported ?? '—' }}</td>
              <td class="td-right">{{ job.records_total ?? '—' }}</td>
              <td
                class="td-right"
                :class="{ 'err-num': (job.rows_failed ?? 0) > 0 }"
              >{{ job.rows_failed ?? '—' }}</td>
              <td class="td-date">{{ fmtDate(job.started_at) }}</td>
              <td class="td-date">{{ fmtDate(job.finished_at) }}</td>
              <td class="muted">{{ duration(job.started_at, job.finished_at) }}</td>
            </tr>

            <tr v-if="!jobs.length">
              <td colspan="10" class="empty-cell">Нет задач ETL</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Error detail modal -->
    <div v-if="errorModal" class="modal-backdrop" @click.self="errorModal = null">
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">Ошибка — Задача #{{ errorModal.id }}</h2>
          <button class="modal-close" @click="errorModal = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="err-meta">
            <span><strong>Источник:</strong> {{ SOURCES[errorModal.source] ?? errorModal.source }}</span>
            <span><strong>Начало:</strong> {{ fmtDate(errorModal.started_at) }}</span>
          </div>
          <pre class="err-pre">{{ errorModal.error_message }}</pre>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="errorModal = null">Закрыть</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-page { min-height: 100vh; background: var(--color-bg); display: flex; flex-direction: column; gap: 0; }

.view-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.view-title { font-size: 18px; font-weight: 700; color: var(--color-text); }
.header-right { display: flex; align-items: center; gap: 10px; }

.auto-badge {
  font-size: 12px;
  color: #2563EB;
  background: #DBEAFE;
  padding: 3px 10px;
  border-radius: 10px;
  font-weight: 600;
}

.btn-refresh {
  background: none;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  padding: 5px 12px;
  font-size: 13px;
  cursor: pointer;
  color: var(--color-text-secondary);
}
.btn-refresh:hover { border-color: var(--color-primary); color: var(--color-primary); }

.alert-error {
  margin: 10px 24px;
  padding: 8px 12px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  font-size: 13px;
}

/* Stats */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  padding: 16px 24px 0;
}
@media (max-width: 700px) { .stats-row { grid-template-columns: 1fr 1fr; } }

.stat-card {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-left: 4px solid var(--color-border);
}
.stat-success { border-left-color: var(--color-success); }
.stat-danger  { border-left-color: var(--color-danger); }
.stat-running { border-left-color: #2563EB; }

.stat-value { font-size: 28px; font-weight: 700; color: var(--color-text); }
.stat-success .stat-value { color: var(--color-success); }
.stat-danger  .stat-value { color: var(--color-danger); }
.stat-running .stat-value { color: #2563EB; }

.stat-label { font-size: 12px; color: var(--color-text-secondary); }

/* Panel & table */
.panel {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin: 16px 24px 24px;
  overflow: hidden;
}
.view-loading { padding: 40px; text-align: center; color: var(--color-text-secondary); }
.table-wrap { overflow-x: auto; }

.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th {
  background: var(--color-bg);
  padding: 8px 10px;
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}
.th-center { text-align: center !important; }
.th-right  { text-align: right !important; }

.data-table td { padding: 8px 10px; border-bottom: 1px solid var(--color-border); vertical-align: middle; }
.td-center  { text-align: center; }
.td-right   { text-align: right; }
.td-id      { color: var(--color-text-secondary); font-size: 11px; }
.td-date    { white-space: nowrap; color: var(--color-text-secondary); font-size: 11px; }
.muted      { color: var(--color-text-secondary); font-size: 11px; }
.err-num    { color: var(--color-danger); font-weight: 700; }

.job-row { transition: background .1s; }
.job-row:hover { background: #F8FAFC; }
.row-running   { background: #F0F7FF; }

.source-badge {
  display: inline-block;
  padding: 2px 7px;
  background: var(--color-bg);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-pulse {
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: .4; transform: scale(.7); }
}

.btn-err {
  background: #FEF2F2;
  border: none;
  border-radius: 4px;
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 12px;
  cursor: pointer;
  color: var(--color-danger);
}
.btn-err:hover { background: #FEE2E2; }

/* Progress bar */
.td-progress { min-width: 100px; }
.progress-wrap {
  position: relative;
  height: 18px;
  background: var(--color-bg);
  border-radius: 4px;
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  border-radius: 4px;
  transition: width .4s;
}
.bar-ok    { background: #34D399; }
.bar-error { background: #F87171; }
.progress-label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: #1F2937;
}

.empty-cell { text-align: center; padding: 32px; color: var(--color-text-secondary); }

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 16px;
}
.modal {
  background: var(--color-surface);
  border-radius: 12px;
  width: 100%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 64px rgba(0,0,0,.22);
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--color-border);
}
.modal-title { font-size: 15px; font-weight: 700; color: var(--color-danger); }
.modal-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--color-text-secondary);
}
.modal-body { padding: 16px 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.err-meta { display: flex; gap: 20px; font-size: 12px; color: var(--color-text-secondary); }
.err-pre {
  background: #FEF2F2;
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  padding: 12px;
  font-size: 12px;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--color-danger);
  max-height: 300px;
  overflow-y: auto;
}
.modal-footer { padding: 12px 20px; border-top: 1px solid var(--color-border); display: flex; justify-content: flex-end; }
.btn-secondary {
  padding: 7px 16px;
  background: none;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  cursor: pointer;
}
</style>
