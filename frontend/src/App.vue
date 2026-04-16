<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth.js'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const showUserBar = computed(() => route.name !== 'login' && auth.isAuthenticated)

async function onLogout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="app-layout" :class="{ 'app-layout--with-user': showUserBar }">
    <div
      v-if="showUserBar"
      class="app-user"
      role="navigation"
      aria-label="Учётная запись"
    >
      <div class="app-user__info">
        <span class="app-user__name">{{ auth.user?.full_name ?? auth.user?.username ?? '–' }}</span>
        <span class="app-user__role">{{ auth.userRole ?? 'viewer' }}</span>
      </div>
      <button type="button" class="app-user__logout" @click="onLogout">
        Выйти
      </button>
    </div>
    <router-view />
  </div>
</template>

<style scoped>
.app-user {
  position: fixed;
  top: 14px;
  right: 24px;
  z-index: 10050;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.app-user__info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1.25;
}
.app-user__name {
  font-size: 13px;
  font-weight: 600;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app-user__role {
  font-size: 11px;
  color: var(--color-text-secondary);
  text-transform: capitalize;
}
.app-user__logout {
  flex-shrink: 0;
  padding: 6px 14px;
  font-size: 13px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text);
}
.app-user__logout:hover {
  background: #f3f4f6;
}
</style>

<style>
/* Жолдаспайтындығы үшін: шапкадағы оң жақ батырмалар мен fixed панель қиылыспасын */
.app-layout--with-user :deep(.dashboard__header),
.app-layout--with-user :deep(.view-header) {
  padding-right: 230px;
}
</style>

<style>
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --color-primary: #1F4E79;
  --color-primary-light: #2E75B6;
  --color-primary-dark: #17375E;
  --color-success: #27AE60;
  --color-warning: #F39C12;
  --color-danger: #E74C3C;
  --color-bg: #F4F6F9;
  --color-surface: #FFFFFF;
  --color-border: #DDE1E7;
  --color-text: #1A1A2E;
  --color-text-secondary: #6B7280;
  --radius: 8px;
  --shadow: 0 1px 4px rgba(0,0,0,.10);
}

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
  line-height: 1.5;
}

a { color: inherit; text-decoration: none; }

button {
  cursor: pointer;
  font-family: inherit;
}
</style>
