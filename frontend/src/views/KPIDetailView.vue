<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import KPIScoreCard from '../components/KPIScoreCard.vue'
import KPITable from '../components/KPITable.vue'
import KPIChart from '../components/KPIChart.vue'
import client from '../api/client.js'
import { KPI_COLORS, KPI_TYPES as KPI_TYPE_LIST, KPI_MAX } from '../utils/kpi.js'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// ── State ──────────────────────────────────────────────────────────────────────
const allRegions   = ref([])
const summaries    = ref([])   // all DGD for selected period
const regionResults = ref([])  // KPIResult[] for selected region (score cards)
const historySummaries = ref([]) // KPISummary[] across time for chart

const loading      = ref(false)
const loadingChart = ref(false)
const error        = ref(null)

// Filters
const selectedRegionCode = ref(route.params.regionCode ?? null)
const selectedKpiType    = ref('')   // '' = all
const dateFrom = ref(firstDayOfYear())
const dateTo   = ref(today())

// ── Constants (from utils) ─────────────────────────────────────────────────────
const KPI_TYPES = [
  { value: '', label: 'Все KPI' },
  ...KPI_TYPE_LIST,
]

// ── Helpers ────────────────────────────────────────────────────────────────────
function today() {
  return new Date().toISOString().slice(0, 10)
}

function firstDayOfYear() {
  return `${new Date().getFullYear()}-01-01`
}

// ── Computed ───────────────────────────────────────────────────────────────────
const visibleRegions = computed(() => {
  const all = allRegions.value.filter(r => !r.is_summary)
  // RLS: viewer only sees assigned regions
  if (auth.userRole === 'viewer' && auth.user?.region_ids?.length) {
    return all.filter(r => auth.user.region_ids.includes(r.id))
  }
  return all
})

const selectedRegion = computed(() =>
  allRegions.value.find(r => r.code === selectedRegionCode.value) ?? null
)

// For score cards: 6 KPIResult objects for the selected region
const scoreCardData = computed(() => {
  const types = ['assessment', 'collection', 'avg_assessment', 'workload', 'long_inspections', 'cancelled']
  const labels = {
    assessment:       'KPI 1 — Доначисление',
    collection:       'KPI 2 — Взыскание',
    avg_assessment:   'KPI 3 — Средняя результативность',
    workload:         'KPI 4 — Нагрузка',
    long_inspections: 'KPI 5 — Длительные проверки',
    cancelled:        'KPI 6 — Отменённые решения',
  }
  return types.map(t => {
    const r = regionResults.value.find(x => x.formula_kpi_type === t)
    return {
      type: t,
      title: labels[t],
      score: r?.score ?? null,
      fact: r?.fact_value ?? null,
      plan: r?.plan_value ?? null,
      pct: r?.pct ?? null,
      maxScore: KPI_MAX[t],
    }
  })
})

// Table rows: summaries of all DGD
const tableRows = computed(() => {
  if (selectedKpiType.value) {
    // Single KPI mode — map KPIResult fields
    return summaries.value
      .filter(s => !s.region_is_summary)
      .map((s, idx) => ({
        ...s,
        region_name: s.region_name,
        score: s[`kpi_${selectedKpiType.value}_score`],
        plan_value: null,
        fact_value: null,
        pct: null,
      }))
  }
  return summaries.value.filter(s => !s.region_is_summary)
})

const tableMode = computed(() =>
  selectedKpiType.value ? 'result' : 'summary'
)

// Chart: score dynamics for selected region over historical summaries
const chartLabels = computed(() =>
  historySummaries.value.map(s => s.date_to)
)

const chartDatasets = computed(() => {
  if (!historySummaries.value.length) return []

  const regionSummaries = historySummaries.value
    .filter(s => s.region_code === selectedRegionCode.value)
    .sort((a, b) => a.date_to.localeCompare(b.date_to))

  if (!regionSummaries.length) return []

  const uniqueDates = [...new Set(regionSummaries.map(s => s.date_to))].sort()

  const byDate = {}
  for (const s of regionSummaries) byDate[s.date_to] = s

  const kpiKeys = selectedKpiType.value
    ? [selectedKpiType.value]
    : ['assessment', 'collection', 'avg_assessment', 'workload', 'long_inspections', 'cancelled']

  const datasets = kpiKeys.map(k => ({
    label: KPI_TYPES.find(t => t.value === k)?.label ?? k,
    data: uniqueDates.map(d => byDate[d]?.[`kpi_${k}_score`] ?? null),
    borderColor: KPI_COLORS[k],
    backgroundColor: KPI_COLORS[k] + '22',
  }))

  // Total line
  datasets.push({
    label: 'Итого',
    data: uniqueDates.map(d => byDate[d]?.total_score ?? null),
    borderColor: KPI_COLORS.total,
    backgroundColor: KPI_COLORS.total + '22',
    borderWidth: 3,
  })

  return datasets
})

const chartLabelsForRegion = computed(() => {
  const regionSummaries = historySummaries.value
    .filter(s => s.region_code === selectedRegionCode.value)
    .sort((a, b) => a.date_to.localeCompare(b.date_to))
  return [...new Set(regionSummaries.map(s => s.date_to))].sort()
})

// ── Data loading ───────────────────────────────────────────────────────────────
async function loadRegions() {
  const { data } = await client.get('/regions/')
  allRegions.value = data.results ?? data
  if (!selectedRegionCode.value && visibleRegions.value.length) {
    selectedRegionCode.value = visibleRegions.value[0].code
  }
}

async function loadSummaries() {
  loading.value = true
  error.value = null
  try {
    const params = { date_from: dateFrom.value, date_to: dateTo.value }
    const [summariesRes, resultsRes] = await Promise.all([
      client.get('/kpi/summaries/', { params }),
      selectedRegionCode.value
        ? client.get('/kpi/results/', {
            params: { ...params, region_code: selectedRegionCode.value },
          })
        : Promise.resolve({ data: { results: [] } }),
    ])
    summaries.value = summariesRes.data.results ?? summariesRes.data
    regionResults.value = resultsRes.data.results ?? resultsRes.data
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки данных'
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  if (!selectedRegionCode.value) return
  loadingChart.value = true
  try {
    // Fetch all summaries for the full year for dynamics chart
    const yearFrom = `${new Date(dateFrom.value).getFullYear()}-01-01`
    const yearTo   = `${new Date(dateTo.value).getFullYear()}-12-31`
    const { data } = await client.get('/kpi/summaries/', {
      params: {
        date_from: yearFrom,
        date_to:   yearTo,
        region_code: selectedRegionCode.value,
      },
    })
    historySummaries.value = data.results ?? data
  } catch {
    historySummaries.value = []
  } finally {
    loadingChart.value = false
  }
}

async function refresh() {
  // Update URL params
  if (selectedRegionCode.value) {
    router.replace({ name: 'kpi-detail', params: { regionCode: selectedRegionCode.value } })
  }
  await loadSummaries()
  await loadHistory()
}

// ── Export stubs (Sprint 14) ───────────────────────────────────────────────────
function exportXLSX() {
  alert('Экспорт XLSX будет реализован в Спринте 14')
}

function exportPDF() {
  alert('Экспорт PDF будет реализован в Спринте 14')
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadRegions()
  await loadSummaries()
  await loadHistory()
})

watch(selectedRegionCode, () => refresh())
</script>

<template>
  <div class="view-page">
    <!-- Header -->
    <header class="view-header">
      <button class="back-btn" @click="router.push({ name: 'dashboard' })">← Дашборд</button>
      <h1 class="view-title">
        Детальный анализ KPI
        <span v-if="selectedRegion" class="view-title__region">
          — {{ selectedRegion.name_ru }}
        </span>
      </h1>

      <div class="header-actions">
        <button class="btn-export" @click="exportXLSX">↓ XLSX</button>
        <button class="btn-export" @click="exportPDF">↓ PDF</button>
      </div>
    </header>

    <!-- Filters -->
    <section class="filters-bar">
      <div class="filter-group">
        <label class="filter-label">С</label>
        <input v-model="dateFrom" type="date" class="filter-input" @change="refresh" />
      </div>
      <div class="filter-group">
        <label class="filter-label">По</label>
        <input v-model="dateTo" type="date" class="filter-input" @change="refresh" />
      </div>
      <div class="filter-group">
        <label class="filter-label">Регион</label>
        <select v-model="selectedRegionCode" class="filter-select">
          <option v-for="r in visibleRegions" :key="r.code" :value="r.code">
            {{ r.name_ru }}
          </option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">KPI</label>
        <select v-model="selectedKpiType" class="filter-select" @change="refresh">
          <option v-for="t in KPI_TYPES" :key="t.value" :value="t.value">
            {{ t.label }}
          </option>
        </select>
      </div>
    </section>

    <div v-if="error" class="alert-error">{{ error }}</div>

    <!-- Score cards for selected region -->
    <section v-if="selectedRegionCode" class="score-cards-section">
      <div class="score-cards-grid">
        <KPIScoreCard
          v-for="card in scoreCardData"
          :key="card.type"
          :title="card.title"
          :score="card.score"
          :fact="card.fact"
          :plan="card.plan"
          :pct="card.pct"
          :max-score="card.maxScore"
        />
      </div>
    </section>

    <!-- Main body: table + chart -->
    <div class="body-grid">
      <!-- Table: all DGD -->
      <section class="panel table-panel">
        <div class="panel-header">
          <h2 class="panel-title">Результаты ДГД</h2>
          <span class="panel-subtitle">{{ dateFrom }} — {{ dateTo }}</span>
        </div>
        <KPITable
          :rows="tableRows"
          :mode="tableMode"
          :loading="loading"
          @row-click="row => router.push({ name: 'kpi-detail', params: { regionCode: row.region_code } })"
        />
      </section>

      <!-- Chart: dynamics -->
      <section class="panel chart-panel">
        <div class="panel-header">
          <h2 class="panel-title">Динамика баллов</h2>
          <span class="panel-subtitle">{{ selectedRegion?.name_ru ?? '' }}</span>
        </div>
        <div v-if="loadingChart" class="chart-loading">Загрузка…</div>
        <div v-else-if="!chartDatasets.length" class="chart-empty">
          Нет исторических данных для построения графика
        </div>
        <div v-else class="chart-wrap">
          <KPIChart
            :labels="chartLabelsForRegion"
            :datasets="chartDatasets"
            :y-max="100"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.view-page {
  min-height: 100vh;
  background: var(--color-bg);
  display: flex;
  flex-direction: column;
}

/* Header */
.view-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.back-btn {
  background: none;
  border: none;
  font-size: 14px;
  color: var(--color-primary);
  cursor: pointer;
  padding: 4px 0;
  white-space: nowrap;
}

.view-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
  flex: 1;
}

.view-title__region {
  font-weight: 400;
  color: var(--color-primary);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.btn-export {
  padding: 6px 14px;
  background: var(--color-surface);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  cursor: pointer;
  color: var(--color-text);
  transition: border-color .15s;
}

.btn-export:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

/* Filters */
.filters-bar {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 10px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.filter-input,
.filter-select {
  padding: 5px 8px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  background: var(--color-surface);
  color: var(--color-text);
  outline: none;
}

.filter-input:focus,
.filter-select:focus {
  border-color: var(--color-primary);
}

/* Error */
.alert-error {
  margin: 12px 24px;
  padding: 10px 14px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  font-size: 13px;
}

/* Score cards */
.score-cards-section {
  padding: 16px 24px 0;
}

.score-cards-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}

@media (max-width: 1200px) {
  .score-cards-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 700px) {
  .score-cards-grid { grid-template-columns: repeat(2, 1fr); }
}

/* Body grid */
.body-grid {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 16px 24px 24px;
}

@media (max-width: 1000px) {
  .body-grid { grid-template-columns: 1fr; }
}

/* Panels */
.panel {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 12px 16px 10px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary);
}

.panel-subtitle {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.table-panel {
  overflow: auto;
}

.chart-panel {
  min-height: 360px;
}

.chart-wrap {
  flex: 1;
  padding: 16px;
}

.chart-loading,
.chart-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  font-size: 14px;
  padding: 32px;
  text-align: center;
}
</style>
