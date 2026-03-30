<script setup>
import { ref, onMounted } from 'vue'
import { KPI_TYPES } from '../utils/kpi.js'
import client from '../api/client.js'

const formulas = ref([])
const loading  = ref(true)
const error    = ref(null)
const showForm = ref(false)
const saving   = ref(false)

// Group formulas by kpi_type → latest first
const byType = ref({})

// New formula form state
const newFormula = ref({
  kpi_type: KPI_TYPES[0].value,
  thresholds: '',
})

async function fetchFormulas() {
  loading.value = true
  error.value = null
  try {
    const { data } = await client.get('/kpi/formulas/')
    formulas.value = data.results ?? data
    // Group by type
    const grouped = {}
    for (const f of formulas.value) {
      if (!grouped[f.kpi_type]) grouped[f.kpi_type] = []
      grouped[f.kpi_type].push(f)
    }
    for (const key of Object.keys(grouped)) {
      grouped[key].sort((a, b) => b.version - a.version)
    }
    byType.value = grouped
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

function openForm(kpiType) {
  newFormula.value = {
    kpi_type: kpiType,
    thresholds: JSON.stringify(
      byType.value[kpiType]?.[0]?.config?.thresholds ?? [],
      null, 2
    ),
  }
  showForm.value = true
  error.value = null
}

async function saveFormula() {
  saving.value = true
  error.value = null
  try {
    let thresholds
    try {
      thresholds = JSON.parse(newFormula.value.thresholds)
    } catch {
      error.value = 'Невалидный JSON в поле порогов'
      return
    }
    await client.post('/kpi/formulas/', {
      kpi_type: newFormula.value.kpi_type,
      config: { thresholds },
    })
    showForm.value = false
    await fetchFormulas()
  } catch (err) {
    error.value = err.response?.data?.detail
      ?? JSON.stringify(err.response?.data)
      ?? 'Ошибка сохранения'
  } finally {
    saving.value = false
  }
}

onMounted(fetchFormulas)

function label(kpiType) {
  return KPI_TYPES.find(t => t.value === kpiType)?.label ?? kpiType
}
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <h1 class="view-title">Управление формулами KPI</h1>
    </header>

    <div v-if="error && !showForm" class="alert-error">{{ error }}</div>

    <div v-if="loading" class="view-loading">Загрузка…</div>

    <div v-else class="formulas-grid">
      <div
        v-for="kpiType in KPI_TYPES.map(t => t.value)"
        :key="kpiType"
        class="formula-card"
      >
        <div class="card-header">
          <span class="card-title">{{ label(kpiType) }}</span>
          <button class="btn-new-version" @click="openForm(kpiType)">+ Версия</button>
        </div>

        <div v-if="!byType[kpiType]?.length" class="no-versions">Версий нет</div>
        <div v-else class="versions-list">
          <div
            v-for="f in byType[kpiType]"
            :key="f.id"
            class="version-row"
            :class="{ 'version-active': f.is_active }"
          >
            <div class="version-meta">
              <span class="version-badge">v{{ f.version }}</span>
              <span v-if="f.is_active" class="active-badge">Активна</span>
              <span class="version-date">{{ f.created_at?.slice(0, 10) }}</span>
              <span class="version-author">{{ f.created_by_display ?? f.created_by ?? '' }}</span>
            </div>
            <div v-if="f.config?.thresholds" class="thresholds">
              <span
                v-for="(th, i) in f.config.thresholds"
                :key="i"
                class="threshold-chip"
              >
                {{ th.pct_from != null ? '≥' + th.pct_from + '%' : '' }}
                {{ th.pct_to != null ? '&lt;' + th.pct_to + '%' : '' }}
                → {{ th.score }}б
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- New version modal -->
    <div v-if="showForm" class="modal-backdrop" @click.self="showForm = false">
      <div class="modal">
        <h2 class="modal-title">Новая версия — {{ label(newFormula.kpi_type) }}</h2>

        <div class="form-group">
          <label class="form-label">Тип KPI</label>
          <select v-model="newFormula.kpi_type" class="form-select">
            <option v-for="t in KPI_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Пороги (JSON)</label>
          <p class="form-hint">Пример: [{"pct_from": 100, "score": 10}, {"pct_from": 90, "score": 5}, {"pct_to": 90, "score": 0}]</p>
          <textarea
            v-model="newFormula.thresholds"
            class="form-textarea"
            rows="8"
            spellcheck="false"
          ></textarea>
        </div>

        <div v-if="error" class="alert-error">{{ error }}</div>

        <div class="modal-actions">
          <button class="btn-secondary" @click="showForm = false">Отмена</button>
          <button class="btn-primary" :disabled="saving" @click="saveFormula">
            {{ saving ? 'Сохранение…' : 'Сохранить' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-page { min-height: 100vh; background: var(--color-bg); display: flex; flex-direction: column; gap: 0; }
.view-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 14px 24px;
}
.view-title { font-size: 18px; font-weight: 700; color: var(--color-text); }
.view-loading { padding: 40px; text-align: center; color: var(--color-text-secondary); }
.alert-error {
  margin: 12px 24px;
  padding: 8px 12px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  font-size: 13px;
}

.formulas-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
  padding: 20px 24px;
}

.formula-card {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}

.card-title { font-size: 13px; font-weight: 600; color: var(--color-primary); }

.btn-new-version {
  padding: 4px 10px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 12px;
  cursor: pointer;
}

.no-versions { padding: 16px; font-size: 13px; color: var(--color-text-secondary); text-align: center; }

.versions-list { padding: 8px 0; }

.version-row {
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border);
  transition: background .12s;
}
.version-row:last-child { border-bottom: none; }
.version-active { background: #F0FDF4; }

.version-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.version-badge {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text);
}

.active-badge {
  background: #D1FAE5;
  color: #065F46;
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 11px;
  font-weight: 600;
}

.version-date, .version-author {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.thresholds { display: flex; flex-wrap: wrap; gap: 4px; }

.threshold-chip {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 11px;
  color: var(--color-text-secondary);
}

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: var(--color-surface);
  border-radius: 12px;
  padding: 28px 28px 20px;
  width: 100%;
  max-width: 560px;
  box-shadow: 0 20px 60px rgba(0,0,0,.25);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.modal-title { font-size: 16px; font-weight: 700; color: var(--color-primary); }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.form-hint { font-size: 11px; color: var(--color-text-secondary); font-family: monospace; margin-bottom: 4px; }
.form-select {
  padding: 7px 10px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  outline: none;
}
.form-select:focus { border-color: var(--color-primary); }
.form-textarea {
  padding: 8px 10px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 12px;
  font-family: monospace;
  outline: none;
  resize: vertical;
}
.form-textarea:focus { border-color: var(--color-primary); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
.btn-primary {
  padding: 8px 20px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary:disabled { opacity: .6; cursor: default; }
.btn-secondary {
  padding: 8px 16px;
  background: none;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 14px;
  cursor: pointer;
  color: var(--color-text);
}
</style>
