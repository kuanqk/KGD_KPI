<script setup>
import { ref, computed } from 'vue'

/**
 * Универсальная таблица KPI-результатов.
 *
 * Режим "summaries" (mode='summary'):
 *   rows[] — массив KPISummary объектов со всеми 6 KPI баллами + total_score + rank
 *
 * Режим "results" (mode='result'):
 *   rows[] — массив KPIResult объектов с plan/fact/pct/score для одного KPI
 */
const props = defineProps({
  rows: {
    type: Array,
    default: () => [],
  },
  mode: {
    type: String,
    default: 'summary',   // 'summary' | 'result'
    validator: v => ['summary', 'result'].includes(v),
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['row-click'])

// ── Sort state ─────────────────────────────────────────────────────────────────
const sortKey = ref(props.mode === 'summary' ? 'rank' : 'score')
const sortDir = ref(1)   // 1 = asc, -1 = desc

function setSort(key) {
  if (sortKey.value === key) {
    sortDir.value *= -1
  } else {
    sortKey.value = key
    sortDir.value = key === 'region_name' ? 1 : -1   // scores default desc
  }
}

// ── Column definitions ─────────────────────────────────────────────────────────
const SUMMARY_COLS = [
  { key: 'rank',                 label: '#',     align: 'center' },
  { key: 'region_name',          label: 'Регион', align: 'left'   },
  { key: 'kpi_assessment_score', label: 'K1',    align: 'center', max: 10  },
  { key: 'kpi_collection_score', label: 'K2',    align: 'center', max: 40  },
  { key: 'kpi_avg_assessment_score', label: 'K3', align: 'center', max: 10 },
  { key: 'kpi_workload_score',   label: 'K4',    align: 'center', max: 15  },
  { key: 'kpi_long_inspections_score', label: 'K5', align: 'center', max: 10 },
  { key: 'kpi_cancelled_score',  label: 'K6',    align: 'center', max: 15  },
  { key: 'total_score',          label: 'Итого', align: 'center', max: 100 },
]

const RESULT_COLS = [
  { key: 'rank',        label: '#',     align: 'center' },
  { key: 'region_name', label: 'Регион', align: 'left'  },
  { key: 'plan_value',  label: 'План',  align: 'right'  },
  { key: 'fact_value',  label: 'Факт',  align: 'right'  },
  { key: 'pct',         label: '%',     align: 'center' },
  { key: 'score',       label: 'Балл',  align: 'center', max: null },
]

const columns = computed(() =>
  props.mode === 'summary' ? SUMMARY_COLS : RESULT_COLS
)

// ── Sorted rows ────────────────────────────────────────────────────────────────
const sortedRows = computed(() => {
  if (!props.rows.length) return []
  return [...props.rows].sort((a, b) => {
    const av = a[sortKey.value] ?? (sortDir.value === 1 ? Infinity : -Infinity)
    const bv = b[sortKey.value] ?? (sortDir.value === 1 ? Infinity : -Infinity)
    if (typeof av === 'string') return av.localeCompare(bv) * sortDir.value
    return (av - bv) * sortDir.value
  })
})

// ── Helpers ────────────────────────────────────────────────────────────────────
function scoreClass(value, max) {
  if (value == null || max == null) return ''
  const pct = (value / max) * 100
  if (pct >= 80) return 'cell-green'
  if (pct >= 50) return 'cell-yellow'
  return 'cell-red'
}

function rankClass(rank) {
  if (rank === 1) return 'rank-gold'
  if (rank === 2) return 'rank-silver'
  if (rank === 3) return 'rank-bronze'
  return ''
}

function fmtNum(v) {
  if (v == null) return '–'
  if (typeof v !== 'number') return v
  if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + ' млн'
  if (Math.abs(v) >= 1_000) return v.toLocaleString('ru-RU', { maximumFractionDigits: 0 })
  return v.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

function fmtScore(v) {
  return v != null ? Math.round(v * 10) / 10 : '–'
}

function cellValue(row, col) {
  const v = row[col.key]
  if (col.key === 'rank') return v ?? '–'
  if (col.key === 'region_name') return v ?? row.region_name_short ?? '–'
  if (col.key === 'pct') return v != null ? fmtNum(v) + '%' : '–'
  if (col.key === 'plan_value' || col.key === 'fact_value') return fmtNum(v)
  return fmtScore(v)
}
</script>

<template>
  <div class="kpi-table-wrap">
    <div v-if="loading" class="loading-rows">
      <div v-for="i in 6" :key="i" class="skeleton-row"></div>
    </div>

    <table v-else class="kpi-table">
      <thead>
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            :class="['th-' + col.align, { 'th-sorted': sortKey === col.key }]"
            :title="col.tooltip"
            @click="setSort(col.key)"
          >
            {{ col.label }}
            <span v-if="sortKey === col.key" class="sort-arrow">
              {{ sortDir === 1 ? '↑' : '↓' }}
            </span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, idx) in sortedRows"
          :key="row.id ?? idx"
          class="kpi-row"
          @click="emit('row-click', row)"
        >
          <td
            v-for="col in columns"
            :key="col.key"
            :class="[
              'td-' + col.align,
              col.key === 'rank' ? rankClass(row.rank) : '',
              col.max != null ? scoreClass(row[col.key], col.max) : '',
            ]"
          >
            <span v-if="col.key === 'rank'" class="rank-badge" :class="rankClass(row.rank)">
              {{ row.rank ?? '–' }}
            </span>
            <template v-else>{{ cellValue(row, col) }}</template>
          </td>
        </tr>
        <tr v-if="!sortedRows.length">
          <td :colspan="columns.length" class="empty-cell">Нет данных</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.kpi-table-wrap {
  overflow-x: auto;
}

.kpi-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.kpi-table th {
  background: var(--color-bg);
  padding: 8px 10px;
  font-weight: 600;
  font-size: 12px;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

.kpi-table th:hover { background: #E8EDF4; }
.th-sorted { color: var(--color-primary) !important; }
.th-center { text-align: center; }
.th-left   { text-align: left;   }
.th-right  { text-align: right;  }

.sort-arrow { margin-left: 4px; font-size: 11px; }

.kpi-table td {
  padding: 7px 10px;
  border-bottom: 1px solid var(--color-border);
}

.td-center { text-align: center; }
.td-left   { text-align: left;   }
.td-right  { text-align: right;  }

.kpi-row {
  cursor: pointer;
  transition: background .12s;
}
.kpi-row:hover { background: #F0F7FF; }

/* Score cell colours */
.cell-green { background: #F0FDF4; color: #166534; font-weight: 600; }
.cell-yellow { background: #FFFBEB; color: #92400E; font-weight: 600; }
.cell-red    { background: #FEF2F2; color: #991B1B; font-weight: 600; }

/* Rank badges */
.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  background: var(--color-bg);
  color: var(--color-text-secondary);
}

.rank-gold   { background: #FEF08A; color: #78350F; }
.rank-silver { background: #E5E7EB; color: #374151; }
.rank-bronze { background: #FDE68A; color: #78350F; }

.empty-cell {
  text-align: center;
  padding: 32px;
  color: var(--color-text-secondary);
}

/* Skeleton */
.loading-rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 0;
}

.skeleton-row {
  height: 34px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
  border-radius: 4px;
}

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
