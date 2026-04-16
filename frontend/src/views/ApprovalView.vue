<script setup>
import { ref, onMounted } from 'vue'
import { KPI_TYPES } from '../utils/kpi.js'
import client from '../api/client.js'
import UserAccount from '../components/UserAccount.vue'

const reports  = ref([])
const loading  = ref(true)
const error    = ref(null)
const acting   = ref({})   // { [id]: true }

// Reject modal
const rejectModal = ref(null)   // { reportId, comment }

async function fetchReports() {
  loading.value = true
  error.value = null
  try {
    const { data } = await client.get('/reports/pending/')
    reports.value = data.results ?? data
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

onMounted(fetchReports)

// ── Actions ────────────────────────────────────────────────────────────────────
async function approve(id) {
  acting.value = { ...acting.value, [id]: true }
  try {
    await client.post(`/reports/${id}/approve/`)
    reports.value = reports.value.filter(r => r.id !== id)
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка утверждения'
  } finally {
    const a = { ...acting.value }; delete a[id]; acting.value = a
  }
}

function openReject(id) {
  rejectModal.value = { reportId: id, comment: '' }
}

async function submitReject() {
  if (!rejectModal.value.comment.trim()) return
  const { reportId, comment } = rejectModal.value
  acting.value = { ...acting.value, [reportId]: true }
  try {
    await client.post(`/reports/${reportId}/reject/`, { comment })
    reports.value = reports.value.filter(r => r.id !== reportId)
    rejectModal.value = null
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка отклонения'
  } finally {
    const a = { ...acting.value }; delete a[reportId]; acting.value = a
  }
}

async function recalculate(id) {
  acting.value = { ...acting.value, [id]: true }
  try {
    await client.post(`/reports/${id}/recalculate/`)
    reports.value = reports.value.filter(r => r.id !== id)
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка запроса пересчёта'
  } finally {
    const a = { ...acting.value }; delete a[id]; acting.value = a
  }
}

function kpiScore(report, type) {
  const v = report[`kpi_${type}_score`]
  return v != null ? Math.round(v * 10) / 10 : '–'
}

function scoreColor(score) {
  if (score == null) return ''
  if (score >= 80) return 'cell-green'
  if (score >= 50) return 'cell-yellow'
  return 'cell-red'
}
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <h1 class="view-title">Согласование отчётов</h1>
      <div class="view-header__right">
        <button class="btn-refresh" @click="fetchReports">↻ Обновить</button>
        <UserAccount />
      </div>
    </header>

    <div v-if="error" class="alert-error">{{ error }}</div>

    <div v-if="loading" class="view-loading">Загрузка…</div>

    <template v-else>
      <div v-if="!reports.length" class="empty-state">
        <span class="empty-icon">✓</span>
        <p>Нет отчётов на рассмотрении</p>
      </div>

      <div v-else class="reports-list">
        <div
          v-for="report in reports"
          :key="report.id"
          class="report-card"
          :class="{ 'card-acting': acting[report.id] }"
        >
          <!-- Card header -->
          <div class="card-header">
            <div class="card-meta">
              <span class="region-name">{{ report.region_name }}</span>
              <span class="period">{{ report.date_from }} — {{ report.date_to }}</span>
            </div>
            <div class="total-score" :class="scoreColor(report.total_score)">
              {{ report.total_score != null ? Math.round(report.total_score) : '–' }}
              <span class="total-label">баллов</span>
            </div>
          </div>

          <!-- KPI scores row -->
          <div class="kpi-row">
            <div
              v-for="t in KPI_TYPES"
              :key="t.value"
              class="kpi-chip"
            >
              <span class="kpi-chip__label">{{ t.short }}</span>
              <span class="kpi-chip__score">{{ kpiScore(report, t.value) }}</span>
            </div>
          </div>

          <!-- Actions -->
          <div class="card-actions">
            <button
              class="btn-approve"
              :disabled="acting[report.id]"
              @click="approve(report.id)"
            >
              ✓ Утвердить
            </button>
            <button
              class="btn-reject"
              :disabled="acting[report.id]"
              @click="openReject(report.id)"
            >
              ✗ Вернуть
            </button>
            <button
              class="btn-recalc"
              :disabled="acting[report.id]"
              @click="recalculate(report.id)"
            >
              ↻ Пересчитать
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- Reject modal -->
    <div v-if="rejectModal" class="modal-backdrop" @click.self="rejectModal = null">
      <div class="modal">
        <h2 class="modal-title">Вернуть отчёт на доработку</h2>
        <div class="form-group">
          <label class="form-label">Комментарий (обязательно)</label>
          <textarea
            v-model="rejectModal.comment"
            class="form-textarea"
            rows="4"
            placeholder="Укажите причину возврата…"
            autofocus
          ></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="rejectModal = null">Отмена</button>
          <button
            class="btn-reject-confirm"
            :disabled="!rejectModal.comment.trim() || acting[rejectModal.reportId]"
            @click="submitReject"
          >
            Вернуть
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-page { min-height: 100vh; background: var(--color-bg); display: flex; flex-direction: column; }

.view-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.view-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.view-title { font-size: 18px; font-weight: 700; color: var(--color-text); }
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
  margin: 12px 24px;
  padding: 8px 12px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  font-size: 13px;
}
.view-loading { padding: 40px; text-align: center; color: var(--color-text-secondary); }

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--color-text-secondary);
  font-size: 15px;
  padding: 60px;
}
.empty-icon { font-size: 48px; color: var(--color-success); }

.reports-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 24px 24px;
}

.report-card {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  transition: opacity .2s;
}
.card-acting { opacity: .6; pointer-events: none; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 10px;
  border-bottom: 1px solid var(--color-border);
}
.card-meta { display: flex; flex-direction: column; gap: 2px; }
.region-name { font-size: 15px; font-weight: 700; color: var(--color-text); }
.period { font-size: 12px; color: var(--color-text-secondary); }

.total-score {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.total-label { font-size: 13px; font-weight: 400; color: var(--color-text-secondary); }
.cell-green { color: var(--color-success); }
.cell-yellow { color: var(--color-warning); }
.cell-red { color: var(--color-danger); }

.kpi-row {
  display: flex;
  gap: 8px;
  padding: 10px 18px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--color-border);
}

.kpi-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--color-bg);
  border-radius: 6px;
  padding: 6px 10px;
  min-width: 48px;
}
.kpi-chip__label { font-size: 10px; font-weight: 700; color: var(--color-text-secondary); }
.kpi-chip__score { font-size: 15px; font-weight: 700; color: var(--color-text); }

.card-actions {
  display: flex;
  gap: 10px;
  padding: 12px 18px;
}

.btn-approve, .btn-reject, .btn-recalc {
  padding: 7px 16px;
  border: none;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity .15s;
}
.btn-approve:disabled, .btn-reject:disabled, .btn-recalc:disabled { opacity: .5; cursor: default; }
.btn-approve { background: #D1FAE5; color: #065F46; }
.btn-approve:hover:not(:disabled) { background: #A7F3D0; }
.btn-reject  { background: #FEE2E2; color: #991B1B; }
.btn-reject:hover:not(:disabled)  { background: #FECACA; }
.btn-recalc  { background: var(--color-bg); color: var(--color-primary); border: 1.5px solid var(--color-border); }
.btn-recalc:hover:not(:disabled)  { border-color: var(--color-primary); }

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: var(--color-surface);
  border-radius: 12px;
  padding: 24px;
  width: 100%;
  max-width: 460px;
  box-shadow: 0 20px 60px rgba(0,0,0,.2);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.modal-title { font-size: 16px; font-weight: 700; color: var(--color-primary); }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.form-textarea {
  padding: 8px 10px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  outline: none;
  resize: vertical;
  font-family: inherit;
}
.form-textarea:focus { border-color: var(--color-primary); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
.btn-secondary {
  padding: 7px 16px;
  background: none;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  cursor: pointer;
}
.btn-reject-confirm {
  padding: 7px 16px;
  background: #E74C3C;
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-reject-confirm:disabled { opacity: .5; cursor: default; }
</style>
