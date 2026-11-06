// Types and loader for public/data/model.json (from pipeline/07_simulate.py).

export type Band = { p10: number[]; p50: number[]; p90: number[] }
export type ScenarioId = 'slow' | 'base' | 'fast'

export type Scenario = {
  label: string
  summary: string
  launch: string
  wardOpen: Record<string, number>
  inZone: number[]
  series: Record<string, Band>
  wardDisplaced: Record<string, number[]>
  hoodAvoided: Record<string, number[]>
  co2Parts: { label: string; value: number }[]
  tornado: { label: string; low: number; high: number }[]
}

export type Model = {
  years: number[]
  scenarios: Record<ScenarioId, Scenario>
  // Free-form evidence block rendered on the Method page.
  evidence: Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any
}

export async function loadModel(): Promise<Model> {
  const res = await fetch('/data/model.json')
  if (!res.ok) throw new Error(`Could not load model.json (${res.status})`)
  return res.json()
}

export const fmt = (v: number) => {
  const a = Math.abs(v)
  if (a === 0) return '0'
  if (a >= 1e6) return `${(v / 1e6).toFixed(a >= 1e7 ? 0 : 1)}M`
  if (a >= 1e4) return `${Math.round(v / 1e3)}k`
  if (a >= 1e3) return `${(v / 1e3).toFixed(1)}k`
  if (a >= 10) return `${Math.round(v)}`
  return v.toFixed(a < 1 && a > 0 ? 2 : 1)
}
