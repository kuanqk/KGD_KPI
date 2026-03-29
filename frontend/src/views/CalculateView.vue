<script setup>
import { ref } from 'vue'
import client from '../api/client.js'

const dateFrom = ref('')
const dateTo = ref('')
const submitting = ref(false)
const result = ref(null)
const error = ref(null)

async function calculate() {
  if (!dateFrom.value || !dateTo.value) return
  submitting.value = true
  error.value = null
  result.value = null
  try {
    const { data } = await client.post('/kpi/calculate/', {
      date_from: dateFrom.value,
      date_to: dateTo.value,
    })
    result.value = data
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка расчёта'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <h1 class="view-title">Расчёт KPI</h1>
    </header>

    <div class="calc-form">
      <div class="form-row">
        <label class="form-label">Дата с</label>
        <input v-model="dateFrom" type="date" class="form-input" />
      </div>
      <div class="form-row">
        <label class="form-label">Дата по</label>
        <input v-model="dateTo" type="date" class="form-input" />
      </div>
      <button class="btn-primary" :disabled="submitting" @click="calculate">
        {{ submitting ? 'Запуск…' : 'Запустить расчёт' }}
      </button>

      <div v-if="error" class="alert-error">{{ error }}</div>
      <div v-if="result" class="alert-success">
        Задача поставлена в очередь. Task ID: <code>{{ result.task_id }}</code>
      </div>
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
.calc-form {
  max-width: 440px;
  margin: 32px auto;
  background: var(--color-surface);
  border-radius: var(--radius);
  padding: 28px;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.form-row { display: flex; flex-direction: column; gap: 6px; }
.form-label { font-size: 13px; font-weight: 600; color: var(--color-text); }
.form-input {
  padding: 8px 12px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 14px;
  outline: none;
}
.form-input:focus { border-color: var(--color-primary); }
.btn-primary {
  padding: 10px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity .2s;
}
.btn-primary:disabled { opacity: .6; cursor: default; }
.alert-error {
  padding: 10px 14px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  font-size: 13px;
}
.alert-success {
  padding: 10px 14px;
  background: #F0FDF4;
  color: var(--color-success);
  border: 1px solid #BBF7D0;
  border-radius: var(--radius);
  font-size: 13px;
}
</style>
