/**
 * DRF cursor pagination: собрать все страницы /kpi/summary/ (в таблице не только первые 50 строк).
 */
import client from '../api/client.js'

function dedupeSummaries(list) {
  const best = new Map()
  for (const s of list) {
    const key = `${s.region_code}|${s.date_from}|${s.date_to}`
    const prev = best.get(key)
    if (!prev || (s.id != null && prev.id != null && s.id > prev.id)) {
      best.set(key, s)
    }
  }
  return [...best.values()]
}

function kpiSummaryPathFromNext(nextAbs) {
  const u = new URL(nextAbs, window.location.origin)
  let p = u.pathname
  if (p.startsWith('/api/v1')) p = p.slice('/api/v1'.length)
  return (p.startsWith('/') ? p : `/${p}`) + u.search
}

export async function fetchAllKpiSummaries(params) {
  let merged = []
  let path = '/kpi/summary/'
  let reqParams = { ...params }
  for (;;) {
    const res = await client.get(path, { params: reqParams })
    const chunk = res.data.results ?? res.data ?? []
    merged = merged.concat(chunk)
    const next = res.data.next
    if (!next) break
    path = kpiSummaryPathFromNext(next)
    reqParams = {}
  }
  return dedupeSummaries(merged)
}

/** Как на дашборде: отчётный год Y = календарный год минус 1. */
export function defaultDashboardReportingYear() {
  return new Date().getFullYear() - 1
}
