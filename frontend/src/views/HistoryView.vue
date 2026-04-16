<script setup>
import { ref, reactive, onMounted } from 'vue'
import client from '../api/client.js'
import UserAccount from '../components/UserAccount.vue'

const reports  = ref([])
const regions  = ref([])
const loading  = ref(false)
const error    = ref(null)

const filters = reactive({
  region: '',
  date_from: (new Date().getFullYear() - 1) + '-01-01',
  date_to:   new Date().toISOString().slice(0, 10),
  status: '',
})

const STATUS_OPTIONS = [
  { value: '',          label: 'Все статусы' },
  { value: 'approved',  label: 'Утверждён' },
  { value: 'rejected',  label: 'Отклонён' },
  { value: 'submitted', label: 'На рассмотрении' },
  { value: 'draft',     label: 'Черновик' },
]

const STATUS_STYLE = {
  approved:  { bg: '#D1FAE5', color: '#065F46', label: 'Утверждён' },
  rejected:  { bg: '#FEE2E2', color: '#991B1B', label: 'Отклонён' },
  submitted: { bg: '#DBEAFE', color: '#1D4ED8', label: 'На рассмотрении' },
  draft:     { bg: '#F3F4F6', color: '#374151', label: 'Черновик' },
}

async function fetchRegions() {
  const { data } = await client.get('/regions/')
  regions.value = (data.results ?? data).filter(r => !r.is_summary)
}

async function fetchReports() {
  loading.value = true
  error.value = null
  try {
    const params = {
      date_from:   filters.date_from || undefined,
      date_to:     filters.date_to   || undefined,
      region_code: filters.region    || undefined,
      status:      filters.status    || undefined,
    }
    const { data } = await client.get('/kpi/summary/', { params })
    reports.value = (data.results ?? data)
      .filter(r => !r.region_is_summary)
      .sort((a, b) => b.date_to?.localeCompare(a.date_to ?? '') ?? 0)
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchRegions()
  await fetchReports()
})

function exportXLSX(id) {
  alert(`Экспорт XLSX (summary ${id}) — будет реализован в Спринте 14`)
}

function exportPDF(id) {
  alert(`Экспорт PDF (summary ${id}) — будет реализован в Спринте 14`)
}

function statusStyle(status) {
  return STATUS_STYLE[status] ?? { bg: '#F3F4F6', color: '#374151', label: status }
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
    <header class="view-header view-header--with-account">
      <h1 class="view-title">История отчётов</h1>
      <UserAccount />
    </header>

    <!-- Filters -->
    <section class="filters-bar">
      <div class="filter-group">
        <label class="filter-label">Регион</label>
        <select v-model="filters.region" class="filter-select" @change="fetchReports">
          <option value="">Все</option>
          <option v-for="r in regions" :key="r.code" :value="r.code">{{ r.name_ru }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">С</label>
        <input v-model="filters.date_from" type="date" class="filter-input" @change="fetchReports" />
      </div>
      <div class="filter-group">
        <label class="filter-label">По</label>
        <input v-model="filters.date_to" type="date" class="filter-input" @change="fetchReports" />
      </div>
      <div class="filter-group">
        <label class="filter-label">Статус</label>
        <select v-model="filters.status" class="filter-select" @change="fetchReports">
          <option v-for="s in STATUS_OPTIONS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </div>
    </section>

    <div v-if="error" class="alert-error">{{ error }}</div>

    <!-- Table -->
    <section class="panel">
      <div v-if="loading" class="view-loading">Загрузка…</div>
      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Регион</th>
              <th>Период</th>
              <th class="th-center">Статус</th>
              <th class="th-center">Итого</th>
              <th class="th-center">K1</th>
              <th class="th-center">K2</th>
              <th class="th-center">K3</th>
              <th class="th-center">K4</th>
              <th class="th-center">K5</th>
              <th class="th-center">K6</th>
              <th class="th-center">Экспорт</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, idx) in reports" :key="r.id">
              <td class="td-num">{{ idx + 1 }}</td>
              <td class="region-name">{{ r.region_name }}</td>
              <td class="nowrap">{{ r.date_from }} — {{ r.date_to }}</td>
              <td class="td-center">
                <span
                  class="status-badge"
                  :style="{ background: statusStyle(r.status).bg, color: statusStyle(r.status).color }"
                >
                  {{ statusStyle(r.status).label }}
                </span>
              </td>
              <td :class="['td-center', scoreColor(r.total_score)]">
                <strong>{{ r.total_score != null ? Math.round(r.total_score) : '–' }}</strong>
              </td>
              <td class="td-center">{{ r.kpi_assessment_score != null ? Math.round(r.kpi_assessment_score) : '–' }}</td>
              <td class="td-center">{{ r.kpi_collection_score != null ? Math.round(r.kpi_collection_score) : '–' }}</td>
              <td class="td-center">{{ r.kpi_avg_assessment_score != null ? Math.round(r.kpi_avg_assessment_score) : '–' }}</td>
              <td class="td-center">{{ r.kpi_workload_score != null ? Math.round(r.kpi_workload_score) : '–' }}</td>
              <td class="td-center">{{ r.kpi_long_inspections_score != null ? Math.round(r.kpi_long_inspections_score) : '–' }}</td>
              <td class="td-center">{{ r.kpi_cancelled_score != null ? Math.round(r.kpi_cancelled_score) : '–' }}</td>
              <td class="td-center">
                <div class="export-btns">
                  <button class="btn-export" title="Экспорт XLSX" @click="exportXLSX(r.id)">XLSX</button>
                  <button class="btn-export" title="Экспорт PDF" @click="exportPDF(r.id)">PDF</button>
                </div>
              </td>
            </tr>
            <tr v-if="!reports.length">
              <td colspan="12" class="empty-cell">Нет отчётов по заданным фильтрам</td>
            </tr>
          </tbody>
        </table>
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

.view-header.view-header--with-account .view-title {
  flex: 1;
  min-width: 0;
}

.filters-bar {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 10px 24px;
  display: flex;
  align-items: center;
  gap: 14px;
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

.alert-error {
  margin: 12px 24px;
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

.data-table td { padding: 8px 10px; border-bottom: 1px solid var(--color-border); }
.td-center { text-align: center; }
.td-num { text-align: center; color: var(--color-text-secondary); font-size: 11px; }
.nowrap { white-space: nowrap; }
.region-name { font-weight: 500; white-space: nowrap; }
.empty-cell { text-align: center; padding: 32px; color: var(--color-text-secondary); }

.cell-green { background: #F0FDF4; color: #166534; }
.cell-yellow { background: #FFFBEB; color: #92400E; }
.cell-red    { background: #FEF2F2; color: #991B1B; }

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.export-btns { display: flex; gap: 4px; justify-content: center; }
.btn-export {
  padding: 2px 8px;
  border: 1.5px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  color: var(--color-text-secondary);
}
.btn-export:hover { border-color: var(--color-primary); color: var(--color-primary); }
</style>
