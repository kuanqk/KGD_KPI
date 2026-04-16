<script setup>
import { ref, computed, onMounted } from 'vue'
import client from '../api/client.js'
import UserAccount from '../components/UserAccount.vue'

const regions  = ref([])
const inputs   = ref([])   // ManualInput[] from API
const loading  = ref(false)
const saving   = ref({})   // { [regionId_year]: true }
const error    = ref(null)
const success  = ref(null)

const selectedYear = ref(new Date().getFullYear())

const years = computed(() => {
  const y = new Date().getFullYear()
  return [y - 1, y, y + 1]
})

// Editable rows: one per region
const rows = computed(() => {
  return regions.value
    .filter(r => !r.is_summary)
    .map(r => {
      const inp = inputs.value.find(
        i => i.region_code === r.code && i.year === selectedYear.value
      )
      return {
        regionId:    r.id,
        regionCode:  r.code,
        regionName:  r.name_ru,
        inputId:     inp?.id ?? null,
        kbkSharePct: inp?.kbk_share_pct ?? '',
        staffCount:  inp?.staff_count ?? '',
        // Track local edits
        _kbk:  inp?.kbk_share_pct ?? '',
        _staff: inp?.staff_count ?? '',
        _dirty: false,
      }
    })
})

// ── Load ───────────────────────────────────────────────────────────────────────
async function fetchRegions() {
  const { data } = await client.get('/regions/')
  regions.value = data.results ?? data
}

async function fetchInputs() {
  loading.value = true
  error.value = null
  try {
    const { data } = await client.get('/etl/manual-inputs/', {
      params: { year: selectedYear.value },
    })
    inputs.value = data.results ?? data
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchRegions()
  await fetchInputs()
})

// ── Editable state (local, not computed) ──────────────────────────────────────
// We need a mutable copy of rows for inline editing
const editRows = ref([])

function buildEditRows() {
  editRows.value = rows.value.map(r => ({ ...r }))
}

// Re-build edit rows when year changes or data loads
import { watch } from 'vue'
watch([inputs, regions], buildEditRows, { immediate: true })

// ── Save ───────────────────────────────────────────────────────────────────────
async function saveRow(row) {
  const key = `${row.regionId}_${selectedYear.value}`
  saving.value = { ...saving.value, [key]: true }
  success.value = null
  error.value = null

  const kbk   = parseFloat(row._kbk)
  const staff = parseInt(row._staff, 10)

  if (isNaN(kbk) || kbk < 0 || kbk > 100) {
    error.value = `${row.regionName}: доля КБК должна быть от 0 до 100`
    const s = { ...saving.value }; delete s[key]; saving.value = s
    return
  }
  if (isNaN(staff) || staff < 0) {
    error.value = `${row.regionName}: штат должен быть положительным числом`
    const s = { ...saving.value }; delete s[key]; saving.value = s
    return
  }

  try {
    const payload = {
      region: row.regionId,
      year: selectedYear.value,
      kbk_share_pct: kbk,
      staff_count: staff,
    }
    if (row.inputId) {
      await client.put(`/etl/manual-inputs/${row.inputId}/`, payload)
    } else {
      const { data } = await client.post('/etl/manual-inputs/', payload)
      row.inputId = data.id
    }
    row._dirty = false
    success.value = `Сохранено: ${row.regionName}`
    setTimeout(() => { success.value = null }, 3000)
  } catch (err) {
    error.value = err.response?.data?.detail
      ?? JSON.stringify(err.response?.data)
      ?? 'Ошибка сохранения'
  } finally {
    const s = { ...saving.value }; delete s[key]; saving.value = s
  }
}

async function saveAll() {
  const dirty = editRows.value.filter(r => r._dirty)
  if (!dirty.length) return
  for (const row of dirty) {
    await saveRow(row)
  }
}

function isSaving(row) {
  return saving.value[`${row.regionId}_${selectedYear.value}`]
}

// Validate kbk sum
const kbkTotal = computed(() =>
  editRows.value.reduce((sum, r) => sum + (parseFloat(r._kbk) || 0), 0)
)
const kbkValid = computed(() => Math.abs(kbkTotal.value - 100) < 0.01)
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <h1 class="view-title">Ручной ввод данных</h1>
      <div class="header-controls">
        <label class="ctrl-label">Год</label>
        <select v-model="selectedYear" class="ctrl-select" @change="fetchInputs">
          <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
        </select>
      </div>
      <UserAccount />
    </header>

    <div class="desc-bar">
      <span>
        Вводится один раз в год. <strong>Доля КБК</strong> — процент от общего плана KPI 1/2 для каждого ДГД.
        <strong>Штат</strong> — количество сотрудников для расчёта KPI 4.
      </span>
      <span
        class="kbk-total"
        :class="kbkValid ? 'kbk-ok' : 'kbk-warn'"
      >
        Σ КБК: {{ kbkTotal.toFixed(2) }}%
        <span v-if="!kbkValid"> ≠ 100%</span>
      </span>
    </div>

    <div v-if="error"   class="alert-error">{{ error }}</div>
    <div v-if="success" class="alert-success">{{ success }}</div>

    <section class="panel">
      <div class="panel-header">
        <span class="panel-subtitle">{{ selectedYear }} год</span>
        <button
          class="btn-save-all"
          :disabled="!editRows.some(r => r._dirty)"
          @click="saveAll"
        >
          Сохранить изменения
        </button>
      </div>

      <div v-if="loading" class="view-loading">Загрузка…</div>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th class="th-num">#</th>
              <th>Регион (ДГД)</th>
              <th class="th-center" title="Доля ДГД по 4 КБК, %. Используется в KPI 1 и KPI 2">
                Доля КБК (%)
              </th>
              <th class="th-center" title="Количество сотрудников. Используется в KPI 4">
                Штат (чел.)
              </th>
              <th class="th-center">Действие</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, idx) in editRows"
              :key="row.regionCode"
              :class="{ 'row-dirty': row._dirty, 'row-saving': isSaving(row) }"
            >
              <td class="td-num">{{ idx + 1 }}</td>
              <td class="region-name">{{ row.regionName }}</td>

              <td class="td-center">
                <input
                  v-model="row._kbk"
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  class="num-input"
                  placeholder="0.00"
                  @input="row._dirty = true"
                />
              </td>

              <td class="td-center">
                <input
                  v-model="row._staff"
                  type="number"
                  min="0"
                  step="1"
                  class="num-input"
                  placeholder="0"
                  @input="row._dirty = true"
                />
              </td>

              <td class="td-center">
                <button
                  v-if="row._dirty"
                  class="btn-save-row"
                  :disabled="isSaving(row)"
                  @click="saveRow(row)"
                >
                  {{ isSaving(row) ? '…' : 'Сохранить' }}
                </button>
                <span v-else class="saved-mark">✓</span>
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr class="total-row">
              <td colspan="2" class="td-right"><strong>Итого (доля КБК)</strong></td>
              <td class="td-center" :class="kbkValid ? 'cell-ok' : 'cell-warn'">
                <strong>{{ kbkTotal.toFixed(2) }}%</strong>
              </td>
              <td colspan="2"></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.view-page { min-height: 100vh; background: var(--color-bg); display: flex; flex-direction: column; gap: 0; }

.view-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.view-title { font-size: 18px; font-weight: 700; color: var(--color-text); flex: 1; }
.header-controls { display: flex; align-items: center; gap: 8px; }
.ctrl-label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.ctrl-select {
  padding: 6px 10px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  outline: none;
}

.desc-bar {
  background: #EFF6FF;
  border-bottom: 1px solid #BFDBFE;
  padding: 8px 24px;
  font-size: 13px;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.kbk-total { font-weight: 700; white-space: nowrap; }
.kbk-ok   { color: var(--color-success); }
.kbk-warn { color: var(--color-warning); }

.alert-error {
  margin: 10px 24px 0;
  padding: 8px 12px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  font-size: 13px;
}
.alert-success {
  margin: 10px 24px 0;
  padding: 8px 12px;
  background: #F0FDF4;
  color: var(--color-success);
  border: 1px solid #BBF7D0;
  border-radius: var(--radius);
  font-size: 13px;
}

.panel {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin: 16px 24px 24px;
  overflow: hidden;
}
.panel-header {
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-subtitle { font-size: 13px; color: var(--color-text-secondary); font-weight: 600; }

.btn-save-all {
  padding: 6px 16px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-save-all:disabled { opacity: .5; cursor: default; }

.view-loading { padding: 40px; text-align: center; color: var(--color-text-secondary); }
.table-wrap { overflow-x: auto; }

.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
  background: var(--color-bg);
  padding: 9px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  text-align: left;
}
.th-center { text-align: center !important; }
.th-num    { text-align: center !important; width: 40px; }

.data-table td { padding: 8px 12px; border-bottom: 1px solid var(--color-border); }
.td-center { text-align: center; }
.td-right  { text-align: right; }
.td-num    { text-align: center; color: var(--color-text-secondary); font-size: 12px; }

.region-name { font-weight: 500; }

.num-input {
  width: 90px;
  padding: 5px 8px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  text-align: right;
  outline: none;
}
.num-input:focus { border-color: var(--color-primary); }

.row-dirty  { background: #FFFBEB; }
.row-saving { opacity: .6; pointer-events: none; }

.btn-save-row {
  padding: 4px 12px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 12px;
  cursor: pointer;
}
.btn-save-row:disabled { opacity: .6; cursor: default; }

.saved-mark { color: var(--color-success); font-size: 16px; }

/* Tfoot */
.total-row { background: var(--color-bg); }
.total-row td { padding: 10px 12px; border-top: 2px solid var(--color-border); }
.cell-ok   { color: var(--color-success); }
.cell-warn { color: var(--color-warning); }
</style>
