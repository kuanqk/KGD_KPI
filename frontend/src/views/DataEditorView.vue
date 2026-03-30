<script setup>
import { ref, reactive, onMounted } from 'vue'
import client from '../api/client.js'

const rows     = ref([])
const regions  = ref([])
const loading  = ref(false)
const saving   = ref({})   // { [id]: true }
const error    = ref(null)

// Filters
const filters = reactive({
  region: '',
  date_from: new Date().getFullYear() + '-01-01',
  date_to:   new Date().toISOString().slice(0, 10),
  management: '',
  is_anomaly: '',
})

const page = ref(1)
const totalCount = ref(0)
const PAGE_SIZE = 50

// ── Load data ──────────────────────────────────────────────────────────────────
async function fetchRegions() {
  const { data } = await client.get('/regions/')
  regions.value = (data.results ?? data).filter(r => !r.is_summary)
}

async function fetchRows(p = 1) {
  loading.value = true
  error.value = null
  try {
    const params = {
      page: p,
      page_size: PAGE_SIZE,
      completed_date_after:  filters.date_from || undefined,
      completed_date_before: filters.date_to   || undefined,
      region_code:           filters.region    || undefined,
      management:            filters.management || undefined,
      is_anomaly:            filters.is_anomaly !== '' ? filters.is_anomaly : undefined,
    }
    const { data } = await client.get('/etl/inspections/completed/', { params })
    rows.value = data.results ?? data
    totalCount.value = data.count ?? rows.value.length
    page.value = p
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchRegions()
  await fetchRows()
})

// ── Inline patch ───────────────────────────────────────────────────────────────
async function patchRow(row, field, value) {
  saving.value = { ...saving.value, [row.id]: true }
  try {
    const { data } = await client.patch(`/etl/inspections/completed/${row.id}/`, { [field]: value })
    Object.assign(row, data)
  } catch {
    // revert
    row[field] = !value
  } finally {
    const s = { ...saving.value }
    delete s[row.id]
    saving.value = s
  }
}

async function toggleAnomaly(row) {
  await patchRow(row, 'is_anomaly', !row.is_anomaly)
}

function fmtMoney(v) {
  if (v == null) return '—'
  if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + ' млн'
  return v.toLocaleString('ru-RU')
}

const totalPages = () => Math.ceil(totalCount.value / PAGE_SIZE)
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <h1 class="view-title">Редактор данных</h1>
      <span class="view-count">Всего записей: {{ totalCount }}</span>
    </header>

    <!-- Filters -->
    <section class="filters-bar">
      <div class="filter-group">
        <label class="filter-label">Регион</label>
        <select v-model="filters.region" class="filter-select" @change="fetchRows()">
          <option value="">Все</option>
          <option v-for="r in regions" :key="r.code" :value="r.code">{{ r.name_ru }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">С</label>
        <input v-model="filters.date_from" type="date" class="filter-input" @change="fetchRows()" />
      </div>
      <div class="filter-group">
        <label class="filter-label">По</label>
        <input v-model="filters.date_to" type="date" class="filter-input" @change="fetchRows()" />
      </div>
      <div class="filter-group">
        <label class="filter-label">Управление</label>
        <select v-model="filters.management" class="filter-select" @change="fetchRows()">
          <option value="">Все</option>
          <option value="УНА">УНА</option>
          <option value="УКН">УКН</option>
          <option value="УНН">УНН</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">Аномалии</label>
        <select v-model="filters.is_anomaly" class="filter-select" @change="fetchRows()">
          <option value="">Все</option>
          <option value="true">Только аномалии</option>
          <option value="false">Без аномалий</option>
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
              <th>Источник</th>
              <th>Регион</th>
              <th>Управление</th>
              <th>Тип</th>
              <th>Дата завершения</th>
              <th class="th-right">Доначислено</th>
              <th class="th-right">Взыскано</th>
              <th class="th-center" title="Учитывается в KPI 3">Учёт (K3)</th>
              <th class="th-center" title="Принято в KPI 1/2">Принято (K1/2)</th>
              <th class="th-center">Аномалия</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.id"
              :class="{ 'row-anomaly': row.is_anomaly, 'row-saving': saving[row.id] }"
            >
              <td><span class="source-badge">{{ row.source?.toUpperCase() }}</span></td>
              <td>{{ row.region_code }}</td>
              <td>{{ row.management }}</td>
              <td>{{ row.form_type }}</td>
              <td class="nowrap">{{ row.completed_date }}</td>
              <td class="td-right">{{ fmtMoney(row.amount_assessed) }}</td>
              <td class="td-right">{{ fmtMoney(row.amount_collected) }}</td>
              <!-- Inline checkboxes -->
              <td class="td-center">
                <input
                  type="checkbox"
                  :checked="row.is_counted"
                  :disabled="saving[row.id]"
                  @change="patchRow(row, 'is_counted', $event.target.checked)"
                />
              </td>
              <td class="td-center">
                <input
                  type="checkbox"
                  :checked="row.is_accepted"
                  :disabled="saving[row.id]"
                  @change="patchRow(row, 'is_accepted', $event.target.checked)"
                />
              </td>
              <td class="td-center">
                <button
                  class="btn-anomaly"
                  :class="{ active: row.is_anomaly }"
                  :disabled="saving[row.id]"
                  :title="row.is_anomaly ? 'Снять отметку аномалии' : 'Пометить как аномалию'"
                  @click="toggleAnomaly(row)"
                >
                  {{ row.is_anomaly ? '⚠' : '○' }}
                </button>
              </td>
            </tr>
            <tr v-if="!rows.length">
              <td colspan="10" class="empty-cell">Нет записей по заданным фильтрам</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages() > 1" class="pagination">
        <button :disabled="page === 1" class="page-btn" @click="fetchRows(page - 1)">←</button>
        <span class="page-info">{{ page }} / {{ totalPages() }}</span>
        <button :disabled="page >= totalPages()" class="page-btn" @click="fetchRows(page + 1)">→</button>
      </div>
    </section>
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
  gap: 16px;
}
.view-title { font-size: 18px; font-weight: 700; color: var(--color-text); }
.view-count { font-size: 13px; color: var(--color-text-secondary); }

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
  margin: 16px 24px 24px;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  flex: 1;
}
.view-loading { padding: 40px; text-align: center; color: var(--color-text-secondary); }
.table-wrap { overflow-x: auto; max-height: calc(100vh - 240px); overflow-y: auto; }

.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th {
  background: var(--color-bg);
  padding: 8px 10px;
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 1;
  white-space: nowrap;
}
.th-center { text-align: center; }
.th-right  { text-align: right; }

.data-table td { padding: 7px 10px; border-bottom: 1px solid var(--color-border); }
.td-center { text-align: center; }
.td-right  { text-align: right; }
.nowrap { white-space: nowrap; }
.empty-cell { text-align: center; padding: 32px; color: var(--color-text-secondary); }

.row-anomaly { background: #FFF7ED; }
.row-saving  { opacity: .6; pointer-events: none; }

.source-badge {
  display: inline-block;
  padding: 1px 6px;
  background: var(--color-bg);
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-secondary);
}

.btn-anomaly {
  background: none;
  border: 1.5px solid var(--color-border);
  border-radius: 4px;
  width: 28px;
  height: 24px;
  font-size: 14px;
  cursor: pointer;
  transition: all .15s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.btn-anomaly.active { background: #FEF3C7; border-color: #F59E0B; color: #92400E; }
.btn-anomaly:hover:not(:disabled) { border-color: var(--color-primary); }

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 10px;
  border-top: 1px solid var(--color-border);
}
.page-btn {
  padding: 4px 12px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-surface);
  cursor: pointer;
  font-size: 14px;
}
.page-btn:disabled { opacity: .4; cursor: default; }
.page-info { font-size: 13px; color: var(--color-text-secondary); }
</style>
