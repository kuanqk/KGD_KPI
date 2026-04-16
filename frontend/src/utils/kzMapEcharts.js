/**
 * Карта РК для ECharts: SVG highcharts-стиля + сопоставление кодов ДГД с slug в SVG.
 * Источник SVG: публичная копия kzmap.svg (см. public/kzmap.svg).
 */
import * as echarts from 'echarts'

/** Центры регионов [долгота, широта] — как в public/kz-regions.geojson (точки для «круглешков»). */
export const REGION_CODE_TO_CENTER = {
  '03xx': [69.4, 53.29],
  '06xx': [57.21, 50.28],
  '09xx': [78.39, 44.02],
  '15xx': [51.88, 47.12],
  '18xx': [82.62, 49.95],
  '60xx': [76.95, 43.23],
  '62xx': [71.45, 51.18],
  '59xx': [69.59, 42.32],
  '21xx': [71.37, 42.9],
  '27xx': [51.37, 51.22],
  '30xx': [73.09, 49.8],
  '39xx': [63.62, 53.21],
  '33xx': [65.49, 44.85],
  '43xx': [52.1, 43.65],
  '71xx': [80.22, 50.43],
  '70xx': [78.38, 45.02],
  '72xx': [67.71, 47.78],
  '45xx': [76.94, 52.29],
  '48xx': [69.14, 54.87],
  '58xx': [68.27, 43.3],
}

/** Границы РК для запасного линейного перевода lng/lat → пиксель */
const KZ_BOUNDS = [
  [46, 40],
  [88, 56],
]

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

/** Цвет маркера как в таблице / старом Leaflet: ≥80 / 50–79 / &lt;50 / нет данных */
function scoreMarkerColor(score) {
  if (score == null || Number.isNaN(Number(score))) return '#9CA3AF'
  const n = Number(score)
  if (n >= 80) return '#27AE60'
  if (n >= 50) return '#F39C12'
  return '#E74C3C'
}

export function buildMarkerOverlayData(mapData) {
  return mapData.map((d) => {
    const center = REGION_CODE_TO_CENTER[d.regionCode]
    const lng = center ? center[0] : 66.9
    const lat = center ? center[1] : 48.0
    const score = d.hasData ? d.value : null
    return {
      lng,
      lat,
      regionCode: d.regionCode,
      displayName: d.displayName,
      hasData: d.hasData,
      score: score != null ? Number(score) : null,
    }
  })
}

/**
 * Пиксель для [lng,lat] на geo SVG: сначала API координатной системы, иначе convertToPixel, иначе линейно по границам РК.
 */
function lngLatToPixel(chart, lng, lat) {
  try {
    const geo = chart.getModel().getComponent('geo', 0)
    const cs = geo?.coordinateSystem
    if (cs && typeof cs.dataToPoint === 'function') {
      const p = cs.dataToPoint([lng, lat])
      if (p && isFinite(p[0]) && isFinite(p[1])) return p
    }
  } catch (_) {
    /* ignore */
  }
  try {
    const pt = chart.convertToPixel({ geoIndex: 0 }, [lng, lat])
    if (pt && isFinite(pt[0]) && isFinite(pt[1])) return pt
  } catch (_) {
    /* ignore */
  }
  const w = chart.getWidth()
  const h = chart.getHeight()
  const [[minLng, minLat], [maxLng, maxLat]] = KZ_BOUNDS
  const x = ((lng - minLng) / (maxLng - minLng)) * w
  const y = ((maxLat - lat) / (maxLat - minLat)) * h
  return [x, y]
}

function buildGraphicMarkers(mapData, chart, onRegionClick) {
  const list = buildMarkerOverlayData(mapData)
  const elements = []
  for (const d of list) {
    const pt = lngLatToPixel(chart, d.lng, d.lat)
    if (!pt) continue
    const fill = scoreMarkerColor(d.score)
    const label =
      d.score != null && !Number.isNaN(Number(d.score)) ? String(Math.round(Number(d.score))) : '–'
    const code = d.regionCode
    elements.push({
      type: 'group',
      id: `kz-marker-${code}`,
      position: pt,
      zlevel: 10,
      z: 10,
      children: [
        {
          type: 'circle',
          shape: { cx: 0, cy: 0, r: 11 },
          style: {
            fill,
            stroke: '#fff',
            lineWidth: 2,
            shadowBlur: 4,
            shadowColor: 'rgba(0,0,0,0.3)',
          },
          cursor: 'pointer',
          onclick: () => onRegionClick(code),
        },
        {
          type: 'text',
          style: {
            text: label,
            x: 0,
            y: 0,
            textAlign: 'center',
            textVerticalAlign: 'middle',
            fill: '#fff',
            font: 'bold 11px sans-serif',
            textShadowColor: 'rgba(0,0,0,0.55)',
            textShadowBlur: 2,
          },
          silent: true,
        },
      ],
    })
  }
  return elements
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
      left: 12,
      top: 12,
      text: ['Больше', 'Меньше'],
      textStyle: { fontSize: 12 },
      calculable: true,
      orient: 'vertical',
      inRange: {
        color: ['#e6f3ff', '#cce7ff', '#99d6ff', '#66c2ff', '#0d81ff', '#0b6edb'],
      },
      show: true,
      seriesIndex: 0,
    },
    geo: {
      map: MAP_NAME,
      roam: true,
      zoom: 1.05,
      scaleLimit: { min: 0.85, max: 3 },
      boundingCoords: KZ_BOUNDS,
      label: { show: false },
      itemStyle: {
        borderColor: '#fff',
        borderWidth: 1,
      },
    },
    series: [
      {
        type: 'map',
        map: MAP_NAME,
        geoIndex: 0,
        data: mapData,
        nameProperty: 'name',
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
              const row = p.data
              return row?.displayName ?? p.name ?? ''
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
  // SVG-карта из registerMap({ svg }) на canvas часто не рисует заливку регионов (пустой фон); graphic-маркеры при этом видны
  const chart = echarts.init(containerEl, null, { renderer: 'svg' })

  const state = {
    mapData,
    onRegionClick,
  }

  const applyMarkers = () => {
    const graphic = buildGraphicMarkers(state.mapData, chart, (code) => state.onRegionClick(code))
    // silent: не триггерить лишние finished (иначе возможна петля setOption → finished → setOption)
    chart.setOption({ graphic }, { replaceMerge: ['graphic'], silent: true })
  }

  const scheduleMarkers = () => {
    requestAnimationFrame(applyMarkers)
  }

  chart.setOption(createRegionMapOption(mapData, maxVal))

  chart.on('georoam', scheduleMarkers)

  scheduleMarkers()
  setTimeout(scheduleMarkers, 50)
  setTimeout(scheduleMarkers, 200)

  const doResize = () => {
    chart.resize()
    scheduleMarkers()
  }
  requestAnimationFrame(() => {
    doResize()
    requestAnimationFrame(doResize)
  })

  chart.on('click', (p) => {
    const code = p.data?.regionCode
    if (code && p.seriesType === 'map') state.onRegionClick(code)
  })

  const onWinResize = () => doResize()
  window.addEventListener('resize', onWinResize)

  const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(doResize) : null
  if (ro) ro.observe(containerEl)

  chart._kzMarkerState = state
  chart._kzScheduleMarkers = scheduleMarkers

  return {
    chart,
    dispose() {
      ro?.disconnect()
      window.removeEventListener('resize', onWinResize)
      chart.off('georoam', scheduleMarkers)
      chart.dispose()
    },
  }
}

export function updateKzRegionMap(chart, summaries) {
  if (!chart) return
  const mapData = buildMapData(summaries)
  const maxVal = getVisualMapMax(mapData)
  if (chart._kzMarkerState) {
    chart._kzMarkerState.mapData = mapData
  }
  chart.setOption(createRegionMapOption(mapData, maxVal))
  requestAnimationFrame(() => {
    chart.resize()
    chart._kzScheduleMarkers?.()
  })
}
