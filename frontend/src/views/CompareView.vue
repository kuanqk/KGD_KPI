<script setup>
import { ref, computed } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import KPIChart from '../components/KPIChart.vue'
import { KPI_COLORS, KPI_TYPES as KPI_TYPE_LIST } from '../utils/kpi.js'
import client from '../api/client.js'

const auth = useAuthStore()

// ── State ──────────────────────────────────────────────────────────────────────
const summariesA = ref([])
const summariesB = ref([])
const loading    = ref(false)
const error      = ref(null)
const searched   = ref(false)

// Period A
const dateFromA = ref(prevYearStart())
const dateToA   = ref(prevYearEnd())

// Period B
const dateFromB = ref(currentYearStart())
const dateToB   = ref(today())

// ── Helpers ────────────────────────────────────────────────────────────────────
function today() { return new Date().toISOString().slice(0, 10) }
function currentYearStart() { return `${new Date().getFullYear()}-01-01` }
function prevYearStart() { return `${new Date().getFullYear() - 1}-01-01` }
function prevYearEnd()   { return `${new Date().getFullYear() - 1}-12-31` }

function fmtScore(v) {
  return v != null ? Math.round(v * 10) / 10 : '–'
}

function delta(a, b) {
  if (a == null || b == null) return null
  return Math.round((b - a) * 10) / 10
}

// ── Computed ───────────────────────────────────────────────────────────────────
const KPI_KEYS = KPI_TYPE_LIST.map(t => t.value)
const KPI_SHORT = Object.fromEntries(KPI_TYPE_LIST.map(t => [t.value, t.short]))

const compareRows = computed(() => {
  if (!summariesA.value.length && !summariesB.value.length) return []

  const byCodeA = {}
  for (const s of summariesA.value) byCodeA[s.region_code] = s
  const byCodeB = {}
  for (const s of summariesB.value) byCodeB[s.region_code] = s

  const codes = [
    ...new Set([
      ...summariesA.value.map(s => s.region_code),
      ...summariesB.value.map(s => s.region_code),
    ]),
  ]

  return codes.map(code => {
    const a = byCodeA[code] ?? null
    const b = byCodeB[code] ?? null
    const name = a?.region_name ?? b?.region_name ?? code
    const isSummary = a?.region_is_summary || b?.region_is_summary

    const kpis = KPI_KEYS.map(k => ({
      key: k,
      short: KPI_SHORT[k],
      scoreA: a?.[`kpi_${k}_score`] ?? null,
      scoreB: b?.[`kpi_${k}_score`] ?? null,
      delta: delta(a?.[`kpi_${k}_score`], b?.[`kpi_${k}_score`]),
    }))

    return {
      code,
      name,
      isSummary,
      rankA: a?.rank ?? null,
      rankB: b?.rank ?? null,
      totalA: a?.total_score ?? null,
      totalB: b?.total_score ?? null,
      totalDelta: delta(a?.total_score, b?.total_score),
      kpis,
    }
  }).sort((a, b) => {
    if (a.isSummary) return 1
    if (b.isSummary) return -1
    return (b.totalB ?? -Infinity) - (a.totalB ?? -Infinity)
  })
})

// Bar chart: delta per region (top 10 by |delta|)
const chartLabels = computed(() =>
  compareRows.value
    .filter(r => !r.isSummary && r.totalDelta != null)
    .slice(0, 20)
    .map(r => r.name)
)

const chartDatasets = computed(() => {
  if (!compareRows.value.length) return []
  const rows = compareRows.value.filter(r => !r.isSummary && r.totalDelta != null).slice(0, 20)
  return [
    {
      label: `Период А (${dateFromA.value} – ${dateToA.value})`,
      data: rows.map(r => r.totalA),
      borderColor: '#64748B',
      backgroundColor: '#64748B22',
    },
    {
      label: `Период Б (${dateFromB.value} – ${dateToB.value})`,
      data: rows.map(r => r.totalB),
      borderColor: KPI_COLORS.total,
      backgroundColor: KPI_COLORS.total + '22',
    },
  ]
})

// ── Actions ────────────────────────────────────────────────────────────────────
async function compare() {
  if (!dateFromA.value || !dateToA.value || !dateFromB.value || !dateToB.value) return
  loading.value = true
  error.value = null
  searched.value = false
  try {
    const [resA, resB] = await Promise.all([
      client.get('/kpi/summaries/', { params: { date_from: dateFromA.value, date_to: dateToA.value } }),
      client.get('/kpi/summaries/', { params: { date_from: dateFromB.value, date_to: dateToB.value } }),
    ])
    summariesA.value = resA.data.results ?? resA.data
    summariesB.value = resB.data.results ?? resB.data
    searched.value = true
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

// ── Colour helpers ─────────────────────────────────────────────────────────────
function scoreColor(score) {
  if (score == null) return ''
  if (score >= 80) return 'cell-green'
  if (score >= 50) return 'cell-yellow'
  return 'cell-red'
}

function deltaClass(d) {
  if (d == null) return ''
  if (d > 0) return 'delta-up'
  if (d < 0) return 'delta-down'
  return 'delta-zero'
}

function deltaArrow(d) {
  if (d == null) return ''
  if (d > 0) return '↑'
  if (d < 0) return '↓'
  return '='
}
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <h1 class="view-title">Сравнение периодов</h1>
    </header>

    <!-- Period pickers -->
    <section class="period-bar">
      <div class="period-block period-a">
        <span class="period-label">Период А</span>
        <input v-model="dateFromA" type="date" class="filter-input" />
        <span class="period-sep">—</span>
        <input v-model="dateToA" type="date" class="filter-input" />
      </div>

      <div class="period-block period-b">
        <span class="period-label">Период Б</span>
        <input v-model="dateFromB" type="date" class="filter-input" />
        <span class="period-sep">—</span>
        <input v-model="dateToB" type="date" class="filter-input" />
      </div>

      <button class="btn-compare" :disabled="loading" @click="compare">
        {{ loading ? 'Загрузка…' : 'Сравнить' }}
      </button>
    </section>

    <div v-if="error" class="alert-error">{{ error }}</div>

    <template v-if="searched">
      <!-- Chart -->
      <section class="panel chart-section">
        <div class="panel-header">
          <h2 class="panel-title">Динамика итоговых баллов</h2>
        </div>
        <div class="chart-wrap">
          <KPIChart
            :labels="chartLabels"
            :datasets="chartDatasets"
            :y-max="100"
          />
        </div>
      </section>

      <!-- Comparison table -->
      <section class="panel table-section">
        <div class="panel-header">
          <h2 class="panel-title">Сравнительная таблица</h2>
          <div class="legend">
            <span class="legend-a">■</span> А: {{ dateFromA }} – {{ dateToA }}
            <span class="legend-b" style="margin-left:12px">■</span> Б: {{ dateFromB }} – {{ dateToB }}
          </div>
        </div>

        <div class="table-wrap">
          <table class="compare-table">
            <thead>
              <tr>
                <th rowspan="2" class="th-left">Регион</th>
                <th colspan="3" class="th-center th-group">Итого</th>
                <th
                  v-for="k in KPI_KEYS"
                  :key="k"
                  colspan="3"
                  class="th-center th-group"
                >{{ KPI_SHORT[k] }}</th>
              </tr>
              <tr>
                <!-- Total sub-headers -->
                <th class="th-center th-sub">А</th>
                <th class="th-center th-sub">Б</th>
                <th class="th-center th-sub">Δ</th>
                <!-- KPI sub-headers -->
                <template v-for="k in KPI_KEYS" :key="k">
                  <th class="th-center th-sub">А</th>
                  <th class="th-center th-sub">Б</th>
                  <th class="th-center th-sub">Δ</th>
                </template>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in compareRows"
                :key="row.code"
                :class="['cmp-row', { 'row-summary': row.isSummary }]"
              >
                <td class="td-left region-name">{{ row.name }}</td>

                <!-- Total -->
                <td :class="['td-center', scoreColor(row.totalA)]">{{ fmtScore(row.totalA) }}</td>
                <td :class="['td-center', scoreColor(row.totalB)]">{{ fmtScore(row.totalB) }}</td>
                <td :class="['td-center delta-cell', deltaClass(row.totalDelta)]">
                  <span v-if="row.totalDelta != null">
                    {{ deltaArrow(row.totalDelta) }} {{ Math.abs(row.totalDelta) }}
                  </span>
                  <span v-else>–</span>
                </td>

                <!-- Per-KPI columns -->
                <template v-for="kpi in row.kpis" :key="kpi.key">
                  <td class="td-center">{{ fmtScore(kpi.scoreA) }}</td>
                  <td class="td-center">{{ fmtScore(kpi.scoreB) }}</td>
                  <td :class="['td-center delta-cell', deltaClass(kpi.delta)]">
                    <span v-if="kpi.delta != null">
                      {{ deltaArrow(kpi.delta) }} {{ Math.abs(kpi.delta) }}
                    </span>
                    <span v-else>–</span>
                  </td>
                </template>
              </tr>

              <tr v-if="!compareRows.length">
                <td colspan="22" class="empty-cell">Нет данных</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <div v-else-if="!loading && !searched" class="hint">
      Выберите два периода и нажмите «Сравнить»
    </div>
  </div>
</template>

<style scoped>
.view-page {
  min-height: 100vh;
  background: var(--color-bg);
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}

.view-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 14px 24px;
}

.view-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
}

/* Period bar */
.period-bar {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.period-block {
  display: flex;
  align-items: center;
  gap: 8px;
}

.period-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-secondary);
  white-space: nowrap;
  min-width: 70px;
}

.period-a .period-label { color: #64748B; }
.period-b .period-label { color: var(--color-primary); }

.period-sep {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.filter-input {
  padding: 5px 8px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  background: var(--color-surface);
  color: var(--color-text);
  outline: none;
}

.filter-input:focus { border-color: var(--color-primary); }

.btn-compare {
  padding: 8px 20px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity .2s;
}

.btn-compare:disabled { opacity: .6; cursor: default; }

/* Alert */
.alert-error {
  margin: 0 24px;
  padding: 10px 14px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  font-size: 13px;
}

/* Hint */
.hint {
  padding: 60px;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 15px;
}

/* Panels */
.panel {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  margin: 0 24px;
}

.panel-header {
  padding: 12px 16px 10px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary);
}

.legend { font-size: 12px; color: var(--color-text-secondary); }
.legend-a { color: #64748B; }
.legend-b { color: var(--color-primary); }

.chart-section { }
.chart-wrap { padding: 16px; height: 280px; }

/* Compare table */
.table-section { }

.table-wrap {
  overflow-x: auto;
  max-height: 520px;
  overflow-y: auto;
}

.compare-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.compare-table th {
  background: var(--color-bg);
  padding: 6px 8px;
  font-weight: 600;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
}

.th-group {
  border-left: 2px solid var(--color-border);
}

.th-sub {
  font-weight: 500;
  font-size: 11px;
}

.th-left  { text-align: left; }
.th-center { text-align: center; }

.compare-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--color-border);
}

.td-center { text-align: center; }
.td-left   { text-align: left; }

.cmp-row { transition: background .12s; }
.cmp-row:hover { background: #F0F7FF; }

.row-summary {
  background: #EFF6FF;
  font-weight: 600;
}

.region-name {
  font-weight: 500;
  color: var(--color-text);
  white-space: nowrap;
}

/* Score colours */
.cell-green { background: #F0FDF4; color: #166534; font-weight: 600; }
.cell-yellow { background: #FFFBEB; color: #92400E; font-weight: 600; }
.cell-red    { background: #FEF2F2; color: #991B1B; font-weight: 600; }

/* Delta */
.delta-cell { font-weight: 600; font-size: 12px; }
.delta-up   { color: #166534; }
.delta-down { color: #991B1B; }
.delta-zero { color: var(--color-text-secondary); }

.empty-cell {
  text-align: center;
  padding: 32px;
  color: var(--color-text-secondary);
}
</style>
