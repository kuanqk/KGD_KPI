/**
 * Карта РК для ECharts: SVG highcharts-стиля + сопоставление кодов ДГД с slug в SVG.
 * Источник SVG: публичная копия kzmap.svg (см. public/kzmap.svg).
 */
import * as echarts from 'echarts'

/** Код региона (как в API) → slug класса highcharts-name-* в SVG */
export const REGION_CODE_TO_SLUG = {
  '03xx': 'акмолинская',
  '06xx': 'актюбинская',
  '09xx': 'алматинская',
  '15xx': 'атырауская',
  '18xx': 'восточно-казахстанская',
  '60xx': 'г.алматы',
  '62xx': 'г.астана',
  '59xx': 'г.шымкент',
  '21xx': 'жамбылская',
  '27xx': 'западно-казахстанская',
  '30xx': 'карагандинская',
  '39xx': 'костанайская',
  '33xx': 'кызылординская',
  '43xx': 'мангистауская',
  '71xx': 'абай',
  '70xx': 'жетісу',
  '72xx': 'ұлытау',
  '45xx': 'павлодарская',
  '48xx': 'северо-казахстанская',
  '58xx': 'туркестанская',
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Добавляет name="…" к path для сопоставления с series.data (как в Orleu). */
export function processKzSvg(svgText) {
  let processed = svgText
  const slugs = [...new Set(Object.values(REGION_CODE_TO_SLUG))]
  for (const svgName of slugs) {
    const escaped = escapeRegExp(svgName)
    const classPattern = new RegExp(`class="([^"]*highcharts-name-${escaped}[^"]*)"`, 'g')
    processed = processed.replace(
      classPattern,
      `class="$1" name="${svgName}"`
    )
  }
  return processed
}

export function buildMapData(summaries) {
  const byCode = {}
  for (const s of summaries) {
    if (s.region_is_summary) continue
    byCode[s.region_code] = s
  }
  const mapData = []
  for (const [code, slug] of Object.entries(REGION_CODE_TO_SLUG)) {
    const s = byCode[code]
    const raw = s?.total_score
    const v = raw != null && !Number.isNaN(Number(raw)) ? Number(raw) : null
    mapData.push({
      name: slug,
      value: v != null ? v : 0,
      regionCode: code,
      displayName: s?.region_name_short ?? s?.region_name ?? code,
      hasData: v != null,
    })
  }
  return mapData
}

export function getVisualMapMax(mapData) {
  const vals = mapData.filter((d) => d.hasData).map((d) => d.value)
  if (!vals.length) return 100
  return Math.max(100, Math.ceil(Math.max(...vals)))
}

const MAP_NAME = 'KazakhstanKPI'

/** Публичный ассет; учитывает Vite `base` (если приложение не в корне домена). */
export function getKzMapSvgUrl() {
  const base = import.meta.env.BASE_URL || '/'
  return (base.endsWith('/') ? base : `${base}/`) + 'kzmap.svg'
}

export function createRegionMapOption(mapData, maxVal) {
  return {
    tooltip: {
      trigger: 'item',
      formatter(params) {
        const d = params.data
        if (d && d.hasData) {
          return `<div style="padding:8px;">
            <strong>${d.displayName}</strong><br/>
            <span style="color:#5470c6">●</span> ${Math.round(d.value).toLocaleString('ru-RU')} баллов
          </div>`
        }
        if (d) {
          return `<div style="padding:8px;"><strong>${d.displayName}</strong><br/>Нет данных</div>`
        }
        return `<div style="padding:8px;">${params.name || ''}</div>`
      },
    },
    visualMap: {
      min: 0,
      max: maxVal,
      left: 10,
      bottom: 24,
      text: ['Больше', 'Меньше'],
      textStyle: { fontSize: 12 },
      calculable: true,
      orient: 'vertical',
      inRange: {
        color: ['#e6f3ff', '#cce7ff', '#99d6ff', '#66c2ff', '#0d81ff', '#0b6edb'],
      },
      show: true,
    },
    series: [
      {
        type: 'map',
        map: MAP_NAME,
        data: mapData,
        nameProperty: 'name',
        roam: true,
        scaleLimit: { min: 0.85, max: 3 },
        zoom: 1.05,
        label: { show: false },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 1,
        },
        emphasis: {
          itemStyle: {
            areaColor: '#e8c547',
            borderColor: '#fff',
            borderWidth: 2,
            shadowBlur: 12,
            shadowColor: 'rgba(0,0,0,0.35)',
          },
          label: {
            show: true,
            fontSize: 12,
            fontWeight: 'bold',
            color: '#8b1538',
            formatter(p) {
              const d = p.data
              return d?.displayName ?? p.name ?? ''
            },
          },
        },
      },
    ],
  }
}

/**
 * Загружает SVG, регистрирует карту, создаёт инстанс, подписывает клик и resize.
 * @returns {{ chart: echarts.ECharts, dispose: () => void }}
 */
export async function initKzRegionMap(containerEl, summaries, { onRegionClick }) {
  const res = await fetch(getKzMapSvgUrl())
  if (!res.ok) throw new Error(`kzmap.svg: ${res.status}`)
  const svgText = await res.text()
  const processed = processKzSvg(svgText)
  echarts.registerMap(MAP_NAME, { svg: processed })

  const mapData = buildMapData(summaries)
  const maxVal = getVisualMapMax(mapData)
  // SVG-карта + registerMap({ svg }) надёжнее с renderer svg; иначе на части окружений canvas даёт пустой вид
  const chart = echarts.init(containerEl, null, { renderer: 'svg' })
  chart.setOption(createRegionMapOption(mapData, maxVal))

  const doResize = () => chart.resize()
  requestAnimationFrame(() => {
    doResize()
    requestAnimationFrame(doResize)
  })

  chart.on('click', (p) => {
    const code = p.data?.regionCode
    if (code) onRegionClick(code)
  })

  const onWinResize = () => doResize()
  window.addEventListener('resize', onWinResize)

  const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(doResize) : null
  if (ro) ro.observe(containerEl)

  return {
    chart,
    dispose() {
      ro?.disconnect()
      window.removeEventListener('resize', onWinResize)
      chart.dispose()
    },
  }
}

export function updateKzRegionMap(chart, summaries) {
  if (!chart) return
  const mapData = buildMapData(summaries)
  const maxVal = getVisualMapMax(mapData)
  chart.setOption(createRegionMapOption(mapData, maxVal))
  requestAnimationFrame(() => chart.resize())
}
