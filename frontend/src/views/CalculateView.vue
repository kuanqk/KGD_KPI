<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import client from '../api/client.js'

const regions    = ref([])
const loading    = ref(false)
const submitting = ref(false)
const error      = ref(null)

// Form
const dateFrom      = ref(new Date().getFullYear() + '-01-01')
const dateTo        = ref(new Date().toISOString().slice(0, 10))
const allRegions    = ref(true)   // checkbox "все регионы"
const selectedIds   = ref([])     // region IDs when allRegions=false

// Task tracking
const taskId     = ref(null)
const taskStatus = ref(null)   // null | 'pending' | 'success' | 'failure'
let pollTimer = null

// ── Load ───────────────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    const { data } = await client.get('/regions/')
    regions.value = (data.results ?? data).filter(r => !r.is_summary)
  } catch { /* ignore */ }
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })

// ── Actions ────────────────────────────────────────────────────────────────────
async function runCalculation() {
  submitting.value = true
  error.value = null
  taskId.value = null
  taskStatus.value = null

  try {
    const payload = {
      date_from: dateFrom.value,
      date_to: dateTo.value,
    }
    if (!allRegions.value && selectedIds.value.length) {
      payload.region_ids = selectedIds.value
    }
    const { data } = await client.post('/kpi/calculate/', payload)
    taskId.value = data.task_id
    taskStatus.value = 'pending'
    startPolling()
  } catch (err) {
    error.value = err.response?.data?.detail
      ?? JSON.stringify(err.response?.data)
      ?? 'Ошибка запуска расчёта'
  } finally {
    submitting.value = false
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  // Poll Celery task status — Django Celery Results endpoint
  pollTimer = setInterval(async () => {
    if (!taskId.value) return
    try {
      const { data } = await client.get(`/kpi/task-status/${taskId.value}/`)
      taskStatus.value = data.status?.toLowerCase() ?? 'pending'
      if (taskStatus.value === 'success' || taskStatus.value === 'failure') {
        clearInterval(pollTimer)
        pollTimer = null
      }
    } catch {
      // status endpoint may not exist yet — treat as pending
    }
  }, 2500)
}

// Submit summary for approval (Sprint 12)
async function submitForApproval() {
  alert('Отправка на утверждение будет реализована в Спринте 12')
}

const canSubmit = computed(() => taskStatus.value === 'success')

function toggleRegion(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx === -1) selectedIds.value.push(id)
  else selectedIds.value.splice(idx, 1)
}
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <h1 class="view-title">Расчёт KPI</h1>
    </header>

    <div class="body">
      <!-- Calculation form -->
      <section class="panel form-panel">
        <div class="panel-header">
          <h2 class="panel-title">Параметры расчёта</h2>
        </div>

        <div class="form-body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Дата с</label>
              <input v-model="dateFrom" type="date" class="form-input" />
            </div>
            <div class="form-group">
              <label class="form-label">Дата по</label>
              <input v-model="dateTo" type="date" class="form-input" />
            </div>
          </div>

          <!-- Region selector -->
          <div class="form-group">
            <label class="form-label">Регионы</label>
            <label class="checkbox-row">
              <input v-model="allRegions" type="checkbox" />
              <span>Все регионы (20 ДГД + КГД)</span>
            </label>
          </div>

          <div v-if="!allRegions" class="region-multiselect">
            <label
              v-for="r in regions"
              :key="r.id"
              class="region-check"
              :class="{ selected: selectedIds.includes(r.id) }"
            >
              <input
                type="checkbox"
                :value="r.id"
                :checked="selectedIds.includes(r.id)"
                @change="toggleRegion(r.id)"
              />
              {{ r.name_ru }}
            </label>
          </div>

          <div v-if="error" class="alert-error">{{ error }}</div>

          <button
            class="btn-primary btn-run"
            :disabled="submitting || taskStatus === 'pending'"
            @click="runCalculation"
          >
            <span v-if="submitting">Запуск…</span>
            <span v-else-if="taskStatus === 'pending'">⟳ Выполняется…</span>
            <span v-else>▶ Запустить расчёт</span>
          </button>
        </div>
      </section>

      <!-- Task status -->
      <section class="panel status-panel">
        <div class="panel-header">
          <h2 class="panel-title">Статус задачи</h2>
        </div>
        <div class="status-body">
          <div v-if="!taskId" class="status-idle">
            <span class="status-icon">⏳</span>
            Запустите расчёт для отображения статуса
          </div>
          <template v-else>
            <div class="task-id">Task ID: <code>{{ taskId }}</code></div>
            <div class="task-status" :class="'status-' + taskStatus">
              <span class="status-icon">
                <span v-if="taskStatus === 'pending'">⟳</span>
                <span v-else-if="taskStatus === 'success'">✓</span>
                <span v-else-if="taskStatus === 'failure'">✗</span>
              </span>
              <span v-if="taskStatus === 'pending'">Выполняется…</span>
              <span v-else-if="taskStatus === 'success'">Расчёт успешно завершён</span>
              <span v-else-if="taskStatus === 'failure'">Ошибка выполнения</span>
            </div>

            <button
              v-if="canSubmit"
              class="btn-submit"
              @click="submitForApproval"
            >
              Отправить на утверждение →
            </button>
          </template>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.view-page { min-height: 100vh; background: var(--color-bg); }
.view-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 14px 24px;
}
.view-title { font-size: 18px; font-weight: 700; color: var(--color-text); }

.body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  padding: 20px 24px;
}
@media (max-width: 800px) { .body { grid-template-columns: 1fr; } }

.panel {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.panel-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}
.panel-title { font-size: 15px; font-weight: 600; color: var(--color-primary); }

.form-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.form-row { display: flex; gap: 16px; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.form-input {
  padding: 7px 10px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  outline: none;
}
.form-input:focus { border-color: var(--color-primary); }

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
}

.region-multiselect {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 8px;
}
.region-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  cursor: pointer;
  padding: 3px 4px;
  border-radius: 4px;
  transition: background .1s;
}
.region-check.selected { background: #EFF6FF; }
.region-check:hover { background: #F0F7FF; }

.alert-error {
  padding: 8px 12px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  font-size: 13px;
}

.btn-primary {
  padding: 10px 20px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary:disabled { opacity: .6; cursor: default; }
.btn-run { width: 100%; justify-content: center; }

/* Status panel */
.status-body { padding: 24px; display: flex; flex-direction: column; gap: 16px; }
.status-idle {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--color-text-secondary);
  font-size: 14px;
}
.task-id { font-size: 12px; color: var(--color-text-secondary); }
.task-id code { font-family: monospace; color: var(--color-text); }

.task-status {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius);
  font-size: 15px;
  font-weight: 600;
}
.status-pending { background: #EFF6FF; color: #1D4ED8; }
.status-success { background: #F0FDF4; color: #166534; }
.status-failure { background: #FEF2F2; color: #991B1B; }

.status-icon { font-size: 18px; }
.status-pending .status-icon { animation: spin 1.2s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }

.btn-submit {
  padding: 10px 20px;
  background: var(--color-success);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity .2s;
}
.btn-submit:hover { opacity: .88; }
</style>
