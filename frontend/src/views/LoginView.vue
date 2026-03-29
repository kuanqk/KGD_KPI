<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const submitting = ref(false)

async function handleSubmit() {
  if (!username.value || !password.value) return
  submitting.value = true
  try {
    await auth.login(username.value, password.value)
    const redirect = route.query.redirect || '/dashboard'
    router.push(redirect)
  } catch {
    // auth.error уже установлен в store
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-card__header">
        <div class="login-card__logo">КГД</div>
        <h1 class="login-card__title">KPI Monitor</h1>
        <p class="login-card__subtitle">Комитет государственных доходов РК</p>
      </div>

      <form class="login-form" @submit.prevent="handleSubmit">
        <div class="form-group">
          <label for="username" class="form-label">Логин</label>
          <input
            id="username"
            v-model="username"
            type="text"
            class="form-input"
            placeholder="Введите логин"
            autocomplete="username"
            :disabled="submitting"
            required
          />
        </div>

        <div class="form-group">
          <label for="password" class="form-label">Пароль</label>
          <input
            id="password"
            v-model="password"
            type="password"
            class="form-input"
            placeholder="Введите пароль"
            autocomplete="current-password"
            :disabled="submitting"
            required
          />
        </div>

        <div v-if="auth.error" class="form-error" role="alert">
          {{ auth.error }}
        </div>

        <button type="submit" class="btn-primary" :disabled="submitting">
          <span v-if="submitting">Вход…</span>
          <span v-else>Войти</span>
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-primary-dark) 0%, var(--color-primary) 60%, var(--color-primary-light) 100%);
}

.login-card {
  background: var(--color-surface);
  border-radius: 16px;
  padding: 48px 40px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 20px 60px rgba(0,0,0,.25);
}

.login-card__header {
  text-align: center;
  margin-bottom: 36px;
}

.login-card__logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  background: var(--color-primary);
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  border-radius: 14px;
  margin-bottom: 16px;
}

.login-card__title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-primary);
}

.login-card__subtitle {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}

.form-input {
  padding: 10px 14px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 15px;
  outline: none;
  transition: border-color .2s;
}

.form-input:focus {
  border-color: var(--color-primary);
}

.form-input:disabled {
  background: var(--color-bg);
  opacity: .7;
}

.form-error {
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  padding: 10px 14px;
  font-size: 13px;
}

.btn-primary {
  padding: 12px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 15px;
  font-weight: 600;
  transition: background .2s, opacity .2s;
  margin-top: 4px;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-light);
}

.btn-primary:disabled {
  opacity: .65;
}
</style>
