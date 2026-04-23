<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import client from '../api/client.js'
import UserAccount from '../components/UserAccount.vue'
import { initKzRegionMap, updateKzRegionMap } from '../utils/kzMapEcharts.js'
import {
  scoreBandColor,
  SCORE_COLOR_GREEN,
  SCORE_COLOR_GREEN_DARK,
  SCORE_COLOR_NO_DATA,
  SCORE_COLOR_ORANGE,
  SCORE_COLOR_RED,
  SCORE_COLOR_YELLOW,
} from '../utils/kpiScoreColors.js'

const router = useRouter()

// ── State ──────────────────────────────────────────────────────────────────────
const summaries = ref([])
const loading = ref(true)
const error = ref(null)
// Отчётный период как в расчёте KPI: 01.01.Y — 01.01.(Y+1), не календарный месяц
const selectedYear = ref(new Date().getFullYear() - 1)

let mapChart = null
let disposeMap = null
const mapLoadError = ref(null)

// ── Constants ──────────────────────────────────────────────────────────────────
const years = computed(() => {
  const current = new Date().getFullYear()
  return [current - 1, current]
})

// ── Computed ───────────────────────────────────────────────────────────────────
const rankedSummaries = computed(() =>
  summaries.value
    .filter(s => !s.region_is_summary)
    .sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999))
)

const kgdSummary = computed(() =>
  summaries.value.find(s => s.region_is_summary) ?? null
)

// ── Helpers ────────────────────────────────────────────────────────────────────
const scoreColor = scoreBandColor

function rankClass(rank) {
  if (rank === 1) return 'rank-gold'
  if (rank === 2) return 'rank-silver'
  if (rank === 3) return 'rank-bronze'
  return ''
}

function kpiVal(summary, key) {
  const score = summary[`kpi_${key}_score`]
  return score != null ? Math.round(score) : '–'
}

/** Убираем повторы одной и той же сводки (на случай дублей в ответе API). */
function dedupeSummaries(list) {
  const best = new Map()
  for (const s of list) {
    const key = `${s.region_code}|${s.date_from}|${s.date_to}`
    const prev = best.get(key)
    if (!prev || (s.id != null && prev.id != null && s.id > prev.id)) {
      best.set(key, s)
    }
  }
  return [...best.values()]
}

/** Преобразует абсолютный next от DRF в путь для axios (baseURL /api/v1). */
function kpiSummaryPathFromNext(nextAbs) {
  const u = new URL(nextAbs, window.location.origin)
  let p = u.pathname
  if (p.startsWith('/api/v1')) p = p.slice('/api/v1'.length)
  return (p.startsWith('/') ? p : `/${p}`) + u.search
}

/** Cursor pagination: собрать все страницы (иначе в таблице только первые 50 строк). */
async function fetchAllKpiSummaries(params) {
  let merged = []
  let path = '/kpi/summary/'
  let reqParams = { ...params }
  for (;;) {
    const res = await client.get(path, { params: reqParams })
    const chunk = res.data.results ?? res.data ?? []
    merged = merged.concat(chunk)
    const next = res.data.next
    if (!next) break
    path = kpiSummaryPathFromNext(next)
    reqParams = {} // курсор уже в query строке path
  }
  return dedupeSummaries(merged)
}

// ── Data loading ───────────────────────────────────────────────────────────────
async function loadData() {
  loading.value = true
  error.value = null
  try {
    const y = selectedYear.value
    const dateFrom = `${y}-01-01`
    const dateTo = `${y + 1}-01-01`

    const params = { date_from: dateFrom, date_to: dateTo, period_exact: 1 }
    summaries.value = await fetchAllKpiSummaries(params)
    if (mapChart) {
      updateKzRegionMap(mapChart, summaries.value)
    }
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки данных'
  } finally {
    loading.value = false
  }
}

// ── Map (ECharts + SVG) ────────────────────────────────────────────────────────
async function initMap() {
  mapLoadError.value = null
  const el = document.getElementById('kz-map')
  if (!el) return
  try {
    const { chart, dispose } = await initKzRegionMap(el, summaries.value, {
      onRegionClick: (code) => goToRegion(code),
    })
    mapChart = chart
    disposeMap = dispose
  } catch (e) {
    console.error(e)
    const msg = e instanceof Error ? e.message : String(e)
    mapLoadError.value = msg.includes('kzmap') || /fetch|network|Failed to fetch/i.test(msg)
      ? 'Не удалось загрузить файл карты (kzmap.svg). Проверьте, что /kzmap.svg отдаётся nginx и попадал в сборку (public/kzmap.svg).'
      : 'Не удалось отобразить карту.'
  }
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadData()
  // Иначе #kz-map ещё с class hidden (display:none) — ECharts получает 0×0 и карта пустая
  await nextTick()
  await initMap()
})

onUnmounted(() => {
  if (disposeMap) {
    disposeMap()
    disposeMap = null
    mapChart = null
  }
})

function onPeriodChange() {
  loadData()
}

function goToRegion(code) {
  router.push({ name: 'kpi-detail', params: { regionCode: code } })
}
</script>

<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="dashboard__header">
      <div>
        <h1 class="dashboard__title">KPI Dashboard</h1>
        <p class="dashboard__subtitle">Комитет государственных доходов РК</p>
      </div>

      <div class="dashboard__controls">
        <label class="ctrl-label">Отчётный период: 01.01.{{ selectedYear }} — 01.01.{{ selectedYear + 1 }}</label>
        <select v-model="selectedYear" class="ctrl-select" @change="onPeriodChange">
          <option v-for="y in years" :key="y" :value="y">{{ y }} (→ {{ y + 1 }})</option>
        </select>
        <UserAccount />
      </div>
    </header>

    <!-- Error -->
    <div v-if="error" class="alert-error">{{ error }}</div>

    <!-- КГД total -->
    <div v-if="kgdSummary" class="kgd-bar">
      <span class="kgd-bar__label">КГД (итого по РК)</span>
      <span
        class="kgd-bar__score"
        :style="{
          color: kgdSummary.total_score != null ? scoreColor(kgdSummary.total_score) : SCORE_COLOR_NO_DATA,
        }"
      >
        {{ kgdSummary.total_score != null ? Math.round(kgdSummary.total_score) + ' баллов' : 'нет данных' }}
      </span>
    </div>

    <!-- Body -->
    <div class="dashboard__body">
      <!-- Map -->
      <section class="panel map-panel">
        <div v-if="loading" class="map-placeholder">Загрузка карты…</div>
        <div v-if="mapLoadError" class="map-error">{{ mapLoadError }}</div>

        <div class="map-legend map-legend--top">
          <span class="map-legend__title">Пороги баллов</span>
          <span class="map-legend__items">
            <span class="legend-item"><span class="legend-dot" :style="{ background: SCORE_COLOR_GREEN_DARK }"></span> 100</span>
            <span class="legend-item"><span class="legend-dot" :style="{ background: SCORE_COLOR_GREEN }"></span> 90–99</span>
            <span class="legend-item"><span class="legend-dot" :style="{ background: SCORE_COLOR_YELLOW }"></span> 76–89</span>
            <span class="legend-item"><span class="legend-dot" :style="{ background: SCORE_COLOR_ORANGE }"></span> 61–75</span>
            <span class="legend-item"><span class="legend-dot" :style="{ background: SCORE_COLOR_RED }"></span> ≤ 60</span>
            <span class="legend-item"><span class="legend-dot" :style="{ background: SCORE_COLOR_NO_DATA }"></span> нет данных</span>
          </span>
          <span class="map-legend__hint">Заливка карты, цвет «Итого» и итог КГД — по одной шкале (как в эталонном Excel).</span>
        </div>

        <div id="kz-map" class="echarts-map" :class="{ hidden: loading }"></div>
      </section>

      <!-- Rating table -->
      <section class="panel rating-panel">
        <h2 class="section-title">Рейтинг ДГД</h2>

        <div v-if="loading" class="loading-rows">
          <div v-for="i in 8" :key="i" class="skeleton-row"></div>
        </div>

        <div v-else class="table-wrap">
          <table class="rating-table">
            <thead>
              <tr>
                <th>#</th>
                <th class="left">Регион</th>
                <th title="Итоговый балл">Итого</th>
                <th title="KPI 1 — Результативность проверок">K1</th>
                <th title="KPI 2 — Собираемость">K2</th>
                <th title="KPI 3 — Средняя результативность">K3</th>
                <th title="KPI 4 — Нагрузка">K4</th>
                <th title="KPI 5 — Длительные проверки">K5</th>
                <th title="KPI 6 — Отменённые решения">K6</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="s in rankedSummaries"
                :key="s.region_code"
                class="rating-row"
                @click="goToRegion(s.region_code)"
              >
                <td>
                  <span class="rank-badge" :class="rankClass(s.rank)">{{ s.rank ?? '–' }}</span>
                </td>
                <td class="left region-name">{{ s.region_name_short ?? s.region_name }}</td>
                <td :style="{ color: scoreColor(s.total_score), fontWeight: 700 }">
                  {{ s.total_score != null ? Math.round(s.total_score) : '–' }}
                </td>
                <td>{{ kpiVal(s, 'assessment') }}</td>
                <td>{{ kpiVal(s, 'collection') }}</td>
                <td>{{ kpiVal(s, 'avg_assessment') }}</td>
                <td>{{ kpiVal(s, 'workload') }}</td>
                <td>{{ kpiVal(s, 'long_inspections') }}</td>
                <td>{{ kpiVal(s, 'cancelled') }}</td>
              </tr>
              <tr v-if="!rankedSummaries.length">
                <td colspan="9" class="empty-cell">Нет данных за выбранный период</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  min-height: 100vh;
  background: var(--color-bg);
  display: flex;
  flex-direction: column;
}

.dashboard__header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 14px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.dashboard__title {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-primary);
}

.dashboard__subtitle {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.dashboard__controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.ctrl-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-right: 4px;
}

.ctrl-select {
  padding: 6px 10px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 14px;
  background: var(--color-surface);
  color: var(--color-text);
  outline: none;
  cursor: pointer;
}

.ctrl-select:focus {
  border-color: var(--color-primary);
}

.alert-error {
  margin: 16px 24px 0;
  padding: 10px 14px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  font-size: 13px;
}

.kgd-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 24px;
  background: #EFF6FF;
  border-bottom: 1px solid #BFDBFE;
  font-size: 13px;
}

.kgd-bar__label {
  font-weight: 600;
  color: var(--color-primary);
}

.kgd-bar__score {
  font-weight: 600;
}

.dashboard__body {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  padding: 20px 24px;
  /* Обе колонки одной высоты: иначе таблица растягивает строку грида, карта в левой
     колонке получает огромный flex-контейнер и SVG оказывается внизу по центру. */
  align-items: stretch;
  --dashboard-panel-h: min(560px, calc(100vh - 200px));
}

@media (max-width: 900px) {
  .dashboard__body {
    grid-template-columns: 1fr;
    --dashboard-panel-h: min(480px, calc(100vh - 240px));
  }
}

.panel {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.echarts-map {
  flex: 1;
  min-height: 0;
  width: 100%;
  min-width: 0;
}

.echarts-map.hidden {
  display: none;
}

.map-placeholder {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.map-error {
  padding: 10px 14px;
  margin: 0;
  background: #FEF2F2;
  color: var(--color-danger);
  border-bottom: 1px solid #FECACA;
  font-size: 13px;
}

.map-panel {
  min-height: 0;
  height: var(--dashboard-panel-h, min(560px, calc(100vh - 200px)));
  max-height: var(--dashboard-panel-h, min(560px, calc(100vh - 200px)));
}

.map-legend--top {
  flex-shrink: 0;
  padding: 10px 16px 12px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
  font-size: 12px;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}

.map-legend__title {
  font-weight: 600;
  color: var(--color-primary);
  margin-right: 4px;
}

.map-legend__items {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.map-legend__hint {
  flex: 1 1 100%;
  font-size: 11px;
  opacity: 0.9;
  line-height: 1.35;
}

.legend-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
}

.rating-panel {
  min-height: 0;
  height: var(--dashboard-panel-h, min(560px, calc(100vh - 200px)));
  max-height: var(--dashboard-panel-h, min(560px, calc(100vh - 200px)));
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  padding: 14px 18px 10px;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-primary);
}

.table-wrap {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.rating-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.rating-table th {
  background: var(--color-bg);
  padding: 7px 8px;
  text-align: center;
  font-weight: 600;
  color: var(--color-text-secondary);
  position: sticky;
  top: 0;
  border-bottom: 1px solid var(--color-border);
  cursor: default;
}

.rating-table th.left,
.rating-table td.left { text-align: left; }

.rating-table td {
  padding: 7px 8px;
  text-align: center;
  border-bottom: 1px solid var(--color-border);
}

.rating-row {
  cursor: pointer;
  transition: background .15s;
}

.rating-row:hover {
  background: #F0F7FF;
}

.region-name {
  font-weight: 500;
  color: var(--color-text);
  white-space: nowrap;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  background: var(--color-bg);
  color: var(--color-text-secondary);
}

.rank-gold   { background: #FEF08A; color: #78350F; }
.rank-silver { background: #E5E7EB; color: #374151; }
.rank-bronze { background: #FDE68A; color: #78350F; }

.empty-cell {
  text-align: center;
  padding: 32px;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.loading-rows {
  padding: 12px 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-row {
  height: 32px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
  border-radius: 4px;
}

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
