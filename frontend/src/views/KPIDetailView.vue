<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import KPIScoreCard from '../components/KPIScoreCard.vue'
import client from '../api/client.js'

const route = useRoute()
const router = useRouter()
const regionCode = route.params.regionCode

const region = ref(null)
const results = ref([])
const loading = ref(true)
const error = ref(null)

const KPI_LABELS = {
  assessment:       'KPI 1 — Результативность проверок',
  collection:       'KPI 2 — Собираемость',
  avg_assessment:   'KPI 3 — Средняя результативность',
  workload:         'KPI 4 — Нагрузка',
  long_inspections: 'KPI 5 — Длительные проверки',
  cancelled:        'KPI 6 — Отменённые решения',
}

onMounted(async () => {
  try {
    const [regRes, resultsRes] = await Promise.all([
      client.get('/regions/'),
      client.get('/kpi/results/', { params: { region_code: regionCode } }),
    ])
    const allRegions = regRes.data.results ?? regRes.data
    region.value = allRegions.find(r => r.code === regionCode) ?? null
    results.value = resultsRes.data.results ?? resultsRes.data
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <button class="back-btn" @click="router.back()">← Назад</button>
      <h1 class="view-title">
        {{ region ? region.name_ru : regionCode }}
      </h1>
    </header>

    <div v-if="loading" class="view-loading">Загрузка…</div>
    <div v-else-if="error" class="alert-error">{{ error }}</div>

    <div v-else class="kpi-grid">
      <KPIScoreCard
        v-for="(label, key) in KPI_LABELS"
        :key="key"
        :title="label"
        :score="results.find(r => r.formula_kpi_type === key)?.score ?? null"
        :max-score="results.find(r => r.formula_kpi_type === key)?.max_score ?? null"
      />
      <p v-if="!results.length" class="empty-text">Нет данных по данному региону</p>
    </div>
  </div>
</template>

<style scoped>
.view-page { min-height: 100vh; background: var(--color-bg); }
.view-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 14px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.back-btn {
  background: none;
  border: none;
  font-size: 14px;
  color: var(--color-primary);
  cursor: pointer;
  padding: 4px 0;
}
.view-title { font-size: 18px; font-weight: 700; color: var(--color-text); }
.view-loading { padding: 40px; text-align: center; color: var(--color-text-secondary); }
.alert-error {
  margin: 16px 24px;
  padding: 10px 14px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  padding: 24px;
}
.empty-text { color: var(--color-text-secondary); font-size: 14px; grid-column: 1/-1; }
</style>
