<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()

async function onLogout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="user-account" role="navigation" aria-label="Учётная запись">
    <div class="user-account__info">
      <span class="user-account__name">{{ auth.user?.full_name ?? auth.user?.username ?? '–' }}</span>
      <span class="user-account__role">{{ auth.userRole ?? 'viewer' }}</span>
    </div>
    <button type="button" class="user-account__logout" @click="onLogout">
      Выйти
    </button>
  </div>
</template>

<style scoped>
.user-account {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 10px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  flex-shrink: 0;
}
.user-account__info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1.25;
}
.user-account__name {
  font-size: 13px;
  font-weight: 600;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-account__role {
  font-size: 11px;
  color: var(--color-text-secondary);
  text-transform: capitalize;
}
.user-account__logout {
  flex-shrink: 0;
  padding: 6px 14px;
  font-size: 13px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text);
}
.user-account__logout:hover {
  background: #f3f4f6;
}
</style>
