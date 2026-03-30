/** KPI types metadata used across multiple views and components */

export const KPI_TYPES = [
  { value: 'assessment',       label: 'KPI 1 — Доначисление',         short: 'K1', max: 10  },
  { value: 'collection',       label: 'KPI 2 — Взыскание',            short: 'K2', max: 40  },
  { value: 'avg_assessment',   label: 'KPI 3 — Среднее доначисление', short: 'K3', max: 10  },
  { value: 'workload',         label: 'KPI 4 — Нагрузка',             short: 'K4', max: 15  },
  { value: 'long_inspections', label: 'KPI 5 — Длительные проверки',  short: 'K5', max: 10  },
  { value: 'cancelled',        label: 'KPI 6 — Отменённые решения',   short: 'K6', max: 15  },
]

/** Stable colour palette — KPI type → hex */
export const KPI_COLORS = {
  assessment:       '#2196F3',
  collection:       '#4CAF50',
  avg_assessment:   '#FF9800',
  workload:         '#9C27B0',
  long_inspections: '#F44336',
  cancelled:        '#009688',
  total:            '#1F4E79',
}

export const KPI_MAX = Object.fromEntries(KPI_TYPES.map(t => [t.value, t.max]))
