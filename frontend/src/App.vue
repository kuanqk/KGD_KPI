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
  <div class="app-layout">
    <div v-if="showUserBar" class="user-bar" role="navigation" aria-label="Учётная запись">
      <span class="user-bar__name" :title="auth.user?.username ?? ''">
        {{ auth.user?.username ?? '–' }}
      </span>
      <button type="button" class="user-bar__logout" @click="onLogout">
        Выйти
      </button>
    </div>
    <router-view />
  </div>
</template>

<style scoped>
.user-bar {
  position: fixed;
  bottom: 16px;
  right: 16px;
  top: auto;
  z-index: 10050;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.user-bar__name {
  font-size: 13px;
  color: var(--color-text-secondary);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-bar__logout {
  padding: 5px 14px;
  font-size: 13px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text);
}
.user-bar__logout:hover {
  background: #f3f4f6;
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
