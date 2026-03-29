<script setup>
import { ref, onMounted } from 'vue'
import client from '../../api/client.js'

const jobs = ref([])
const loading = ref(true)
const error = ref(null)

const STATUS_COLORS = {
  pending:    '#9CA3AF',
  running:    '#3B82F6',
  done:       '#27AE60',
  failed:     '#E74C3C',
  partial:    '#F39C12',
}

onMounted(async () => {
  try {
    const { data } = await client.get('/etl/jobs/')
    jobs.value = data.results ?? data
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
      <h1 class="view-title">Мониторинг ETL</h1>
    </header>

    <div v-if="loading" class="view-loading">Загрузка…</div>
    <div v-else-if="error" class="alert-error">{{ error }}</div>

    <div v-else class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Источник</th>
            <th>Статус</th>
            <th>Запущен</th>
            <th>Завершён</th>
            <th>Загружено</th>
            <th>Ошибок</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in jobs" :key="job.id">
            <td>{{ job.id }}</td>
            <td>{{ job.source }}</td>
            <td>
              <span
                class="status-dot"
                :style="{ background: STATUS_COLORS[job.status] ?? '#9CA3AF' }"
              ></span>
              {{ job.status }}
            </td>
            <td class="nowrap">{{ job.started_at ? new Date(job.started_at).toLocaleString('ru-RU') : '—' }}</td>
            <td class="nowrap">{{ job.finished_at ? new Date(job.finished_at).toLocaleString('ru-RU') : '—' }}</td>
            <td>{{ job.rows_loaded ?? '—' }}</td>
            <td :style="{ color: job.rows_failed > 0 ? 'var(--color-danger)' : 'inherit' }">
              {{ job.rows_failed ?? '—' }}
            </td>
          </tr>
          <tr v-if="!jobs.length">
            <td colspan="7" class="empty-cell">Нет задач ETL</td>
          </tr>
        </tbody>
      </table>
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
.view-loading { padding: 40px; text-align: center; color: var(--color-text-secondary); }
.alert-error {
  margin: 16px 24px;
  padding: 10px 14px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
}
.table-wrap { padding: 20px 24px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; background: var(--color-surface); border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow); }
.data-table th { background: var(--color-bg); padding: 10px 12px; text-align: left; font-size: 12px; font-weight: 600; color: var(--color-text-secondary); border-bottom: 1px solid var(--color-border); }
.data-table td { padding: 9px 12px; border-bottom: 1px solid var(--color-border); }
.nowrap { white-space: nowrap; }
.empty-cell { text-align: center; padding: 24px; color: var(--color-text-secondary); }
.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
</style>
