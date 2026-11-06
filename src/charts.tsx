import { useState } from 'react'
import { fmt, type Band } from './model'

const W = 340
const H = 150
const M = { l: 40, r: 10, t: 10, b: 20 }

function niceTicks(lo: number, hi: number, n = 4): number[] {
  const span = hi - lo || 1
  const raw = span / n
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
  // Round outward so the axis always contains the data.
  const first = Math.floor(lo / step + 1e-9)
  const last = Math.ceil(hi / step - 1e-9)
  const out: number[] = []
  for (let i = first; i <= last; i++) out.push(i * step)
  return out
}

type Props = {
  title: string
  unit: string
  years: number[]
  band: Band
  color: string
  year: number
  reference?: { label: string; values: number[] }
  format?: (v: number) => string
}

/** Median line with a P10-P90 band, a marker on the selected year and a hover crosshair. */
export function FanChart({ title, unit, years, band, color, year, reference, format = fmt }: Props) {
  const [hover, setHover] = useState<number | null>(null)
  const all = [...band.p10, ...band.p90, ...(reference?.values ?? []), 0]
  const ticks = niceTicks(Math.min(...all), Math.max(...all))
  const lo = ticks[0]
  const hi = ticks[ticks.length - 1]
  const x = (i: number) => M.l + (i / (years.length - 1)) * (W - M.l - M.r)
  const y = (v: number) => H - M.b - ((v - lo) / (hi - lo || 1)) * (H - M.t - M.b)
  const line = (a: number[]) => a.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')
  const area =
    band.p90.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('') +
    [...band.p10].reverse().map((v, i) => `L${x(years.length - 1 - i).toFixed(1)},${y(v).toFixed(1)}`).join('') +
    'Z'
  const sel = years.indexOf(year)
  const at = hover ?? sel
  return (
    <figure className="chart">
      <figcaption>
        <strong>{title}</strong>
        <span>{unit}</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${title}. In ${years[at]}: median ${format(band.p50[at])}, range ${format(band.p10[at])} to ${format(band.p90[at])}.`}
        onPointerMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect()
          const f = ((e.clientX - r.left) / r.width) * W
          const i = Math.round(((f - M.l) / (W - M.l - M.r)) * (years.length - 1))
          setHover(Math.max(0, Math.min(years.length - 1, i)))
        }}
        onPointerLeave={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} className={t === 0 ? 'axis-zero' : 'grid'} />
            <text x={M.l - 6} y={y(t) + 3} textAnchor="end" className="tick">
              {format(t)}
            </text>
          </g>
        ))}
        {years.map((yr, i) =>
          yr % 2 === 0 ? (
            <text key={yr} x={x(i)} y={H - 6} textAnchor="middle" className="tick">
              {`'${String(yr).slice(2)}`}
            </text>
          ) : null,
        )}
        <path d={area} fill={color} opacity={0.22} />
        {reference && <path d={line(reference.values)} className="ref-line" />}
        <path d={line(band.p50)} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
        <line x1={x(at)} x2={x(at)} y1={M.t} y2={H - M.b} className="crosshair" />
        <circle cx={x(at)} cy={y(band.p50[at])} r={4} fill={color} stroke="var(--surface)" strokeWidth={2} />
      </svg>
      <p className="readout-line">
        <b>{years[at]}</b> median <b>{format(band.p50[at])}</b>
        <span>
          {' '}
          range {format(band.p10[at])} to {format(band.p90[at])}
        </span>
        {reference && (
          <span>
            {' '}
            · {reference.label} {format(reference.values[at])}
          </span>
        )}
      </p>
    </figure>
  )
}

type Row = { label: string; value: number }

/** Ranked list with one thin bar per row. */
export function RankList({ title, unit, rows, color, format = fmt }: { title: string; unit: string; rows: Row[]; color: string; format?: (v: number) => string }) {
  const max = Math.max(...rows.map((r) => r.value), 1e-6)
  return (
    <figure className="chart">
      <figcaption>
        <strong>{title}</strong>
        <span>{unit}</span>
      </figcaption>
      <ol className="rank">
        {rows.map((r) => (
          <li key={r.label}>
            <span className="rank-label">{r.label}</span>
            <span className="rank-value">{format(r.value)}</span>
            <i style={{ width: `${(r.value / max) * 100}%`, background: color }} />
          </li>
        ))}
      </ol>
    </figure>
  )
}

/** Colour key for a map layer. */
export function Scale({ label, from, to, max }: { label: string; from: string; to: string; max: string }) {
  return (
    <div className="scale">
      <span>{label}</span>
      <i style={{ background: `linear-gradient(to right, ${from}, ${to})` }} />
      <div>
        <small>0</small>
        <small>{max}</small>
      </div>
    </div>
  )
}

/** Signed horizontal bars around zero: the parts that add up to a net figure. */
export function PartsChart({ title, unit, rows, format = fmt }: { title: string; unit: string; rows: Row[]; format?: (v: number) => string }) {
  const max = Math.max(...rows.map((r) => Math.abs(r.value)), 1)
  return (
    <figure className="chart">
      <figcaption>
        <strong>{title}</strong>
        <span>{unit}</span>
      </figcaption>
      <ul className="parts">
        {rows.map((r) => (
          <li key={r.label} title={`${r.label}: ${format(r.value)}`}>
            <span className="parts-label">{r.label}</span>
            <span className="parts-track">
              <i
                className={r.label === 'Net' ? 'net' : 'part'}
                style={{
                  width: `${(Math.abs(r.value) / max) * 50}%`,
                  left: r.value >= 0 ? '50%' : `${50 - (Math.abs(r.value) / max) * 50}%`,
                }}
              />
            </span>
            <span className="parts-value">
              {r.value > 0 ? '+' : ''}
              {format(r.value)}
            </span>
          </li>
        ))}
      </ul>
    </figure>
  )
}

/** One-at-a-time sensitivity: how far each input moves the result. */
export function Tornado({ title, unit, rows, format = fmt }: { title: string; unit: string; rows: { label: string; low: number; high: number }[]; format?: (v: number) => string }) {
  const max = Math.max(...rows.flatMap((r) => [Math.abs(r.low), Math.abs(r.high)]), 1)
  const pos = (v: number) => 50 + (v / max) * 50
  return (
    <figure className="chart">
      <figcaption>
        <strong>{title}</strong>
        <span>{unit}</span>
      </figcaption>
      <ul className="parts">
        {rows.map((r) => {
          const a = pos(Math.min(r.low, r.high))
          const b = pos(Math.max(r.low, r.high))
          return (
            <li key={r.label} title={`${r.label}: ${format(r.low)} to ${format(r.high)}`}>
              <span className="parts-label">{r.label}</span>
              <span className="parts-track">
                <i className="range" style={{ left: `${a}%`, width: `${Math.max(b - a, 0.6)}%` }} />
              </span>
              <span className="parts-value">
                {format(r.low)} to {format(r.high)}
              </span>
            </li>
          )
        })}
      </ul>
    </figure>
  )
}

/** Plain two-series line chart for the evidence page (actual against fitted). */
export function EvidenceLine({ title, unit, labels, actual, fit, color }: { title: string; unit: string; labels: string[]; actual: number[]; fit?: number[]; color: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const ticks = niceTicks(0, Math.max(...actual, ...(fit ?? [])))
  const hi = ticks[ticks.length - 1]
  const x = (i: number) => M.l + (i / (labels.length - 1)) * (W - M.l - M.r)
  const y = (v: number) => H - M.b - (v / (hi || 1)) * (H - M.t - M.b)
  const line = (a: number[]) => a.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')
  const at = hover ?? labels.length - 1
  return (
    <figure className="chart">
      <figcaption>
        <strong>{title}</strong>
        <span>{unit}</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={title}
        onPointerMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect()
          const i = Math.round(((((e.clientX - r.left) / r.width) * W - M.l) / (W - M.l - M.r)) * (labels.length - 1))
          setHover(Math.max(0, Math.min(labels.length - 1, i)))
        }}
        onPointerLeave={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} className={t === 0 ? 'axis-zero' : 'grid'} />
            <text x={M.l - 6} y={y(t) + 3} textAnchor="end" className="tick">
              {fmt(t)}
            </text>
          </g>
        ))}
        {labels.map((l, i) =>
          l.endsWith('-01') ? (
            <text key={l} x={x(i)} y={H - 6} textAnchor="middle" className="tick">
              {l.slice(0, 4)}
            </text>
          ) : null,
        )}
        {fit && <path d={line(fit)} className="ref-line" />}
        <path d={line(actual)} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
        <line x1={x(at)} x2={x(at)} y1={M.t} y2={H - M.b} className="crosshair" />
        <circle cx={x(at)} cy={y(actual[at])} r={4} fill={color} stroke="var(--surface)" strokeWidth={2} />
      </svg>
      <p className="readout-line">
        <b>{labels[at]}</b> actual <b>{fmt(actual[at])}</b>
        {fit && <span> · fitted {fmt(fit[at])}</span>}
      </p>
    </figure>
  )
}
