/**
 * Цвет «Итого» / карты по эталону Excel (old/260423): два зелёных с 90+, жёлтый 76–89,
 * оранжевый 61–75, красный ≤60, серый — нет данных.
 */

export const SCORE_COLOR_NO_DATA = '#9CA3AF'
export const SCORE_COLOR_RED = '#E74C3C'
export const SCORE_COLOR_ORANGE = '#F39C12'
export const SCORE_COLOR_YELLOW = '#F1C40F'
/** 90–99 баллов */
export const SCORE_COLOR_GREEN = '#27AE60'
/** 100 баллов — более тёмный зелёный */
export const SCORE_COLOR_GREEN_DARK = '#1E8448'

/**
 * @param {number|null|undefined} score — итог 0…100 (или null)
 * @returns {string} hex цвет
 */
export function scoreBandColor(score) {
  if (score == null || Number.isNaN(Number(score))) return SCORE_COLOR_NO_DATA
  const n = Math.round(Number(score))
  if (n <= 60) return SCORE_COLOR_RED
  if (n <= 75) return SCORE_COLOR_ORANGE
  if (n <= 89) return SCORE_COLOR_YELLOW
  if (n < 100) return SCORE_COLOR_GREEN
  return SCORE_COLOR_GREEN_DARK
}

/**
 * Для карты: без данных — серый, иначе как у «Итого».
 */
export function regionFillColor(score, hasData) {
  if (!hasData) return SCORE_COLOR_NO_DATA
  return scoreBandColor(score)
}
