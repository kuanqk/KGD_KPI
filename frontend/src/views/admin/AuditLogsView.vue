<script setup>
import { ref, onMounted } from 'vue'
import client from '../../api/client.js'

const logs = ref([])
const loading = ref(true)
const error = ref(null)
const cursor = ref(null)
const hasMore = ref(false)

async function fetchLogs(cursorParam = null) {
  loading.value = true
  try {
    const params = {}
    if (cursorParam) params.cursor = cursorParam
    const { data } = await client.get('/admin/audit-logs/', { params })
    logs.value = cursorParam ? [...logs.value, ...(data.results ?? [])] : (data.results ?? data)
    cursor.value = data.next ? new URL(data.next).searchParams.get('cursor') : null
    hasMore.value = !!data.next
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

onMounted(() => fetchLogs())

function loadMore() {
  if (cursor.value) fetchLogs(cursor.value)
}
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <h1 class="view-title">Журнал действий</h1>
    </header>

    <div v-if="error" class="alert-error">{{ error }}</div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Время</th>
            <th>Пользователь</th>
            <th>Действие</th>
            <th>IP</th>
            <th>Детали</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id">
            <td class="nowrap">{{ new Date(log.created_at).toLocaleString('ru-RU') }}</td>
            <td>{{ log.user_display ?? log.user ?? '—' }}</td>
            <td><span class="action-badge">{{ log.action }}</span></td>
            <td class="nowrap">{{ log.ip_address ?? '—' }}</td>
            <td class="details">{{ log.extra ? JSON.stringify(log.extra) : '—' }}</td>
          </tr>
          <tr v-if="!loading && !logs.length">
            <td colspan="5" class="empty-cell">Нет записей</td>
          </tr>
        </tbody>
      </table>

      <div v-if="loading" class="view-loading">Загрузка…</div>

      <button v-if="hasMore && !loading" class="load-more-btn" @click="loadMore">
        Загрузить ещё
      </button>
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
.view-loading { padding: 20px; text-align: center; color: var(--color-text-secondary); font-size: 14px; }
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
.details { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-text-secondary); font-family: monospace; font-size: 11px; }
.empty-cell { text-align: center; padding: 24px; color: var(--color-text-secondary); }
.action-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; background: var(--color-bg); color: var(--color-text-secondary); }
.load-more-btn {
  margin: 16px auto;
  display: block;
  padding: 8px 24px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  cursor: pointer;
}
</style>
