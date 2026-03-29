<script setup>
import { ref, onMounted } from 'vue'
import client from '../../api/client.js'

const users = ref([])
const loading = ref(true)
const error = ref(null)

onMounted(async () => {
  try {
    const { data } = await client.get('/admin/users/')
    users.value = data.results ?? data
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
      <h1 class="view-title">Пользователи</h1>
    </header>

    <div v-if="loading" class="view-loading">Загрузка…</div>
    <div v-else-if="error" class="alert-error">{{ error }}</div>

    <div v-else class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Логин</th>
            <th>ФИО</th>
            <th>Роль</th>
            <th>Регион</th>
            <th>Активен</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.id }}</td>
            <td>{{ u.username }}</td>
            <td>{{ u.full_name ?? '—' }}</td>
            <td><span class="role-badge" :class="`role-${u.role}`">{{ u.role }}</span></td>
            <td>{{ u.region_ids?.length ? u.region_ids.join(', ') : '—' }}</td>
            <td>{{ u.is_active ? '✓' : '✗' }}</td>
          </tr>
          <tr v-if="!users.length">
            <td colspan="6" class="empty-cell">Нет пользователей</td>
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
.data-table td { padding: 10px 12px; border-bottom: 1px solid var(--color-border); }
.empty-cell { text-align: center; padding: 24px; color: var(--color-text-secondary); }
.role-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.role-admin { background: #EDE9FE; color: #6D28D9; }
.role-operator { background: #DBEAFE; color: #1D4ED8; }
.role-reviewer { background: #D1FAE5; color: #065F46; }
.role-viewer { background: #F3F4F6; color: #374151; }
</style>
