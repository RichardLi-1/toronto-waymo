// Loads public/data/trips.json (from pipeline/06_routes.py) and shapes it for deck.gl.

type TripsFile = {
  sample: number
  day: string
  routes: number[][]
  // route, start minute, duration in minutes, origin ward, destination ward (0 = outside the city), uniform draw, spare
  trips: [number, number, number, number, number, number, number][]
  active: number[]
}

export type Trip = {
  path: Float64Array
  timestamps: Float32Array
  start: number
  end: number
  origin: number
  dest: number
  draw: number
}

export type TripDay = { sample: number; label: string; trips: Trip[]; active: number[] }

export const MINUTES = 24 * 60

function decode(deltas: number[]): Float64Array {
  const out = new Float64Array(deltas.length)
  let x = 0
  let y = 0
  for (let i = 0; i < deltas.length; i += 2) {
    x += deltas[i]
    y += deltas[i + 1]
    out[i] = x / 1e5
    out[i + 1] = y / 1e5
  }
  return out
}

export async function loadTrips(url = '/data/trips.json'): Promise<TripDay> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Could not load ${url} (${res.status})`)
  const file: TripsFile = await res.json()
  const paths = file.routes.map(decode)
  const dists = paths.map((p) => {
    const d = new Float32Array(p.length / 2)
    for (let i = 1; i < d.length; i++) {
      const dx = (p[i * 2] - p[i * 2 - 2]) * 0.72 // cos(43.7 deg)
      const dy = p[i * 2 + 1] - p[i * 2 - 1]
      d[i] = d[i - 1] + Math.hypot(dx, dy)
    }
    return d
  })
  const trips = file.trips.map(([r, start, dur, origin, dest, draw]): Trip => {
    const d = dists[r]
    const total = d[d.length - 1] || 1
    const timestamps = new Float32Array(d.length)
    // Spread the trip's duration along the route in proportion to distance.
    for (let i = 0; i < d.length; i++) timestamps[i] = start + (dur * d[i]) / total
    return { path: paths[r], timestamps, start, end: start + dur, origin, dest, draw }
  })
  return { sample: file.sample, label: file.day, trips, active: file.active }
}

/** Trips in motion at each minute, for trips that pass the filter. */
export function activeByMinute(trips: Trip[], keep: (t: Trip) => boolean): Int32Array {
  const diff = new Int32Array(MINUTES + 2)
  for (const t of trips) {
    if (!keep(t)) continue
    const s = Math.floor(t.start)
    const e = Math.min(Math.floor(t.end), MINUTES)
    diff[s]++
    diff[e + 1]--
  }
  const out = new Int32Array(MINUTES)
  let run = 0
  for (let m = 0; m < MINUTES; m++) {
    run += diff[m]
    out[m] = run
  }
  return out
}
