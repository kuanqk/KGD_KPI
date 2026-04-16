<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import client from '../api/client.js'
import L from 'leaflet'

const router = useRouter()
const auth = useAuthStore()

// ── State ──────────────────────────────────────────────────────────────────────
const summaries = ref([])
const loading = ref(true)
const error = ref(null)
// Отчётный период как в расчёте KPI: 01.01.Y — 01.01.(Y+1), не календарный месяц
const selectedYear = ref(new Date().getFullYear() - 1)

let map = null
let markersLayer = null

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
function scoreColor(score) {
  if (score == null) return '#9CA3AF'
  if (score >= 80) return '#27AE60'
  if (score >= 50) return '#F39C12'
  return '#E74C3C'
}

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

// ── Data loading ───────────────────────────────────────────────────────────────
async function loadData() {
  loading.value = true
  error.value = null
  try {
    const y = selectedYear.value
    const dateFrom = `${y}-01-01`
    const dateTo = `${y + 1}-01-01`

    const res = await client.get('/kpi/summary/', {
      params: { date_from: dateFrom, date_to: dateTo },
    })
    summaries.value = res.data.results ?? res.data
    updateMapMarkers()
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки данных'
  } finally {
    loading.value = false
  }
}

// ── Map ────────────────────────────────────────────────────────────────────────
function initMap() {
  map = L.map('kz-map', {
    center: [48.0, 66.9],
    zoom: 5,
    zoomControl: true,
    attributionControl: false,
  })

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    opacity: 0.45,
  }).addTo(map)

  markersLayer = L.layerGroup().addTo(map)

  fetch('/kz-regions.geojson')
    .then(r => r.json())
    .then(geojson => {
      map._geojson = geojson
      updateMapMarkers()
    })
}

function updateMapMarkers() {
  if (!map || !markersLayer || !map._geojson) return
  markersLayer.clearLayers()

  const summaryByCode = {}
  for (const s of summaries.value) {
    summaryByCode[s.region_code] = s
  }

  for (const feature of map._geojson.features) {
    const code = feature.properties.code
    const summary = summaryByCode[code]
    const score = summary?.total_score ?? null
    const [lng, lat] = feature.geometry.coordinates

    const color = scoreColor(score)
    const circle = L.circleMarker([lat, lng], {
      radius: 20,
      fillColor: color,
      color: '#fff',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.85,
    })

    const label = score != null ? Math.round(score) : '–'
    circle.bindTooltip(
      `<strong>${feature.properties.name_short}</strong><br>${label} баллов`,
      { permanent: false, direction: 'top' }
    )
    circle.on('click', () => {
      router.push({ name: 'kpi-detail', params: { regionCode: code } })
    })
    circle.addTo(markersLayer)

    // Score label on top of circle
    const icon = L.divIcon({
      className: '',
      html: `<div class="map-label">${label}</div>`,
      iconSize: [40, 40],
      iconAnchor: [20, 20],
    })
    L.marker([lat, lng], { icon, interactive: false }).addTo(markersLayer)
  }
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadData()
  initMap()
})

onUnmounted(() => {
  if (map) {
    map.remove()
    map = null
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
        <label class="ctrl-label">Отчётный год (период 01.01—01.01)</label>
        <select v-model="selectedYear" class="ctrl-select" @change="onPeriodChange">
          <option v-for="y in years" :key="y" :value="y">{{ y }} (→ {{ y + 1 }})</option>
        </select>

        <div class="user-badge">
          <span class="user-badge__name">{{ auth.user?.full_name ?? auth.user?.username ?? '–' }}</span>
          <span class="user-badge__role">{{ auth.userRole ?? 'viewer' }}</span>
        </div>
      </div>
    </header>

    <!-- Error -->
    <div v-if="error" class="alert-error">{{ error }}</div>

    <!-- КГД total -->
    <div v-if="kgdSummary" class="kgd-bar">
      <span class="kgd-bar__label">КГД (итого по РК)</span>
      <span class="kgd-bar__score">
        {{ kgdSummary.total_score != null ? Math.round(kgdSummary.total_score) + ' баллов' : 'нет данных' }}
      </span>
    </div>

    <!-- Body -->
    <div class="dashboard__body">
      <!-- Map -->
      <section class="panel">
        <div v-if="loading" class="map-placeholder">Загрузка карты…</div>
        <div id="kz-map" class="leaflet-map" :class="{ hidden: loading }"></div>

        <div class="map-legend">
          <span class="legend-dot" style="background:#27AE60"></span> ≥ 80
          <span class="legend-dot" style="background:#F39C12; margin-left:10px"></span> 50–79
          <span class="legend-dot" style="background:#E74C3C; margin-left:10px"></span> &lt; 50
          <span class="legend-dot" style="background:#9CA3AF; margin-left:10px"></span> нет данных
        </div>
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

.user-badge {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  padding: 4px 10px;
  background: var(--color-bg);
  border-radius: var(--radius);
}

.user-badge__name {
  font-size: 13px;
  font-weight: 600;
}

.user-badge__role {
  font-size: 11px;
  color: var(--color-text-secondary);
  text-transform: capitalize;
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
  color: var(--color-primary);
}

.dashboard__body {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  padding: 20px 24px;
}

@media (max-width: 900px) {
  .dashboard__body { grid-template-columns: 1fr; }
}

.panel {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.leaflet-map {
  flex: 1;
  min-height: 380px;
}

.leaflet-map.hidden {
  display: none;
}

.map-placeholder {
  flex: 1;
  min-height: 380px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.map-legend {
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
  border-top: 1px solid var(--color-border);
}

.legend-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.rating-panel {
  min-height: 420px;
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

<style>
.map-label {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  pointer-events: none;
  text-shadow: 0 1px 2px rgba(0,0,0,.5);
}
</style>
