<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
  score: {
    type: Number,
    default: null,
  },
  fact: {
    type: [Number, String],
    default: null,
  },
  plan: {
    type: [Number, String],
    default: null,
  },
  pct: {
    type: Number,
    default: null,
  },
  maxScore: {
    type: Number,
    default: null,
  },
})

function scoreColor(score) {
  if (score == null) return 'var(--color-text-secondary)'
  if (score >= 80) return 'var(--color-success)'
  if (score >= 50) return 'var(--color-warning)'
  return 'var(--color-danger)'
}

function progressWidth(score, maxScore) {
  if (score == null) return '0%'
  const max = maxScore ?? 100
  return Math.min((score / max) * 100, 100) + '%'
}

function progressColor(score) {
  if (score == null) return 'var(--color-border)'
  if (score >= 80) return 'var(--color-success)'
  if (score >= 50) return 'var(--color-warning)'
  return 'var(--color-danger)'
}

function fmt(val) {
  if (val == null) return '–'
  if (typeof val === 'number') {
    return val >= 1000
      ? val.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
      : val.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
  }
  return val
}
</script>

<template>
  <div class="kpi-card">
    <div class="kpi-card__header">
      <span class="kpi-card__title">{{ title }}</span>
      <span
        class="kpi-card__score"
        :style="{ color: scoreColor(score) }"
      >
        {{ score != null ? Math.round(score) : '–' }}
        <span v-if="maxScore" class="kpi-card__max">/ {{ maxScore }}</span>
      </span>
    </div>

    <!-- Progress bar -->
    <div class="kpi-card__bar-track">
      <div
        class="kpi-card__bar-fill"
        :style="{
          width: progressWidth(score, maxScore),
          background: progressColor(score),
        }"
      ></div>
    </div>

    <!-- Fact / Plan -->
    <div class="kpi-card__meta">
      <div class="kpi-meta-item">
        <span class="kpi-meta-item__label">Факт</span>
        <span class="kpi-meta-item__value">{{ fmt(fact) }}</span>
      </div>
      <div class="kpi-meta-item">
        <span class="kpi-meta-item__label">План</span>
        <span class="kpi-meta-item__value">{{ fmt(plan) }}</span>
      </div>
      <div v-if="pct != null" class="kpi-meta-item">
        <span class="kpi-meta-item__label">%</span>
        <span
          class="kpi-meta-item__value"
          :style="{ color: pct >= 100 ? 'var(--color-success)' : 'var(--color-danger)' }"
        >{{ fmt(pct) }}%</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kpi-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: box-shadow .2s;
}

.kpi-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,.08);
}

.kpi-card__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.kpi-card__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
  line-height: 1.3;
}

.kpi-card__score {
  font-size: 28px;
  font-weight: 700;
  white-space: nowrap;
  flex-shrink: 0;
}

.kpi-card__max {
  font-size: 14px;
  font-weight: 400;
  color: var(--color-text-secondary);
}

.kpi-card__bar-track {
  height: 6px;
  background: var(--color-border);
  border-radius: 3px;
  overflow: hidden;
}

.kpi-card__bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width .5s ease;
}

.kpi-card__meta {
  display: flex;
  gap: 16px;
}

.kpi-meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kpi-meta-item__label {
  font-size: 11px;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.kpi-meta-item__value {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}
</style>
