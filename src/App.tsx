import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import DeckGL from '@deck.gl/react'
import { ColumnLayer, GeoJsonLayer, ScatterplotLayer } from '@deck.gl/layers'
import { TripsLayer } from '@deck.gl/geo-layers'
import type { MapViewState } from '@deck.gl/core'
import { Map as BaseMap } from 'react-map-gl/maplibre'
import './maplibre'
import { activeByMinute, loadTrips, MINUTES, type Trip, type TripDay } from './trips'
import { fmt, loadModel, type Model, type Scenario, type ScenarioId } from './model'
import { FanChart, PartsChart, RankList, Scale, Tornado } from './charts'
import { DayTimeline } from './Timeline'
import { Method } from './Method'
import './App.css'

const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
const WAYMO: [number, number, number] = [60, 232, 212]
const HUMAN: [number, number, number] = [236, 146, 52]
const TEAL = '#14a899'
const ORANGE = '#d97512'
const TRAIL = 9

type View = 'streets' | 'drivers' | 'safety' | 'climate'
const VIEWS: { id: View; label: string }[] = [
  { id: 'streets', label: 'Streets' },
  { id: 'drivers', label: 'Uber & Lyft' },
  { id: 'safety', label: 'Collisions' },
  { id: 'climate', label: 'CO₂' },
]
const SCENARIOS: ScenarioId[] = ['slow', 'base', 'fast']
const SPEEDS = [
  { label: '5 min/s', value: 5 },
  { label: '15 min/s', value: 15 },
  { label: '30 min/s', value: 30 },
]

// ?year=2035&scenario=base&view=streets&t=17:30&paused
const params = new URLSearchParams(window.location.search)
const START_MIN = (() => {
  const m = /^(\d{1,2}):(\d{2})$/.exec(params.get('t') ?? '')
  return m ? Number(m[1]) * 60 + Number(m[2]) : 7 * 60
})()

const INITIAL_VIEW: MapViewState = { longitude: -79.4, latitude: 43.685, zoom: 10.6, pitch: 35, bearing: -17 }

type Feature = { properties: Record<string, number | string> }
const lerp = (a: number[], b: number[], f: number) => a.map((v, i) => Math.round(v + (b[i] - v) * f)) as [number, number, number]
const clock = (m: number) => `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(Math.floor(m % 60)).padStart(2, '0')}`

function Tile({ value, label, note }: { value: string; label: string; note?: string }) {
  return (
    <div className="tile">
      <b>{value}</b>
      <span>{label}</span>
      {note && <small>{note}</small>}
    </div>
  )
}

type Names = { wards: Record<string, string>; hoods: Record<string, string> }
type PanelProps = { view: View; model: Model; sc: Scenario; year: number; names: Names }

const top = (table: Record<string, number[]>, yi: number, names: Record<string, string>) =>
  Object.entries(table)
    .map(([k, v]) => ({ label: names[k] ?? k, value: v[yi] }))
    .filter((r) => r.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 5)
const peakOf = (table: Record<string, number[]>, yi: number) => Math.max(0, ...Object.values(table).map((v) => v[yi]))

const Panel = memo(function Panel({ view, model, sc, year, names }: PanelProps) {
  const yi = model.years.indexOf(year)
  const s = sc.series
  const at = (k: string) => s[k].p50[yi]
  const span = (k: string) => `${fmt(s[k].p10[yi])} to ${fmt(s[k].p90[yi])}`
  const c = model.evidence.constants
  const props = { years: model.years, year }
  if (view === 'streets')
    return (
      <>
        <h2>How many Waymos?</h2>
        <p className="lede">
          {at('waymoTrips') < 1
            ? `No paid service yet in this scenario. Median start: ${sc.launch}.`
            : `By ${year}, about ${fmt(at('fleet'))} cars carrying ${fmt(at('waymoTrips'))} trips a day. That is ${at('share').toFixed(1)}% of ride-hailing in Toronto.`}
        </p>
        <div className="tiles">
          <Tile value={fmt(at('fleet'))} label="cars in the fleet" note={span('fleet')} />
          <Tile value={`${at('share').toFixed(1)}%`} label="of ride-hail trips" note={`${s.share.p10[yi].toFixed(1)}% to ${s.share.p90[yi].toFixed(1)}%`} />
        </div>
        <FanChart {...props} title="Waymo trips per day" unit="median, P10 to P90" band={s.waymoTrips} color={TEAL} />
        <FanChart {...props} title="Fleet size" unit="cars" band={s.fleet} color={TEAL} />
      </>
    )
  if (view === 'drivers')
    return (
      <>
        <h2>Uber and Lyft</h2>
        <p className="lede">
          {at('displaced') < 1
            ? 'No trips displaced yet.'
            : `Drivers do ${fmt(at('displaced'))} fewer trips a day than they would without Waymo. Total Uber and Lyft trips ${at('human') >= s.human.p50[0] ? 'still sit above' : 'fall below'} the 2026 level, because the market keeps growing.`}
        </p>
        <div className="tiles">
          <Tile value={fmt(at('fte'))} label="full-time-equivalent driver jobs" note={span('fte')} />
          <Tile value={`$${fmt(at('fares'))}M`} label="fares a year moved to Waymo" note={`$${fmt(s.fares.p10[yi])}M to $${fmt(s.fares.p90[yi])}M`} />
        </div>
        <FanChart {...props} title="Uber and Lyft trips per day" unit="dashed: no Waymo" band={s.human} color={ORANGE} reference={{ label: 'no Waymo', values: s.baseline.p50 }} />
        <FanChart {...props} title="Driver jobs displaced" unit="full-time equivalents" band={s.fte} color={ORANGE} />
        {at('displaced') >= 1 && (
          <>
            <RankList title="Most affected wards" unit="trips displaced a day" rows={top(sc.wardDisplaced, yi, names.wards)} color={ORANGE} />
            <Scale label="Map: trips displaced a day, by pickup ward" from="#78481e" to="#faaa50" max={fmt(peakOf(sc.wardDisplaced, yi))} />
          </>
        )}
        <p className="note">Jobs use {c.minApp.toFixed(0)} in-app minutes per trip and a 40-hour week. Fares are in 2026 dollars and include HST and City fees.</p>
      </>
    )
  if (view === 'safety') {
    const pct = (at('injury') / c.injYear) * 100
    return (
      <>
        <h2>Collisions</h2>
        <p className="lede">
          {at('injury') < 0.5
            ? 'No change yet.'
            : `About ${fmt(at('injury'))} fewer injury collisions a year, or ${pct.toFixed(1)}% of Toronto's total. Ride-hailing is only about 4.5% of the driving in the city, so a much safer driver can only move the total so far.`}
        </p>
        <div className="tiles">
          <Tile value={fmt(at('injury'))} label="injury collisions avoided a year" note={span('injury')} />
          <Tile value={at('ksi').toFixed(1)} label="fatal or serious collisions avoided" note={`${s.ksi.p10[yi].toFixed(1)} to ${s.ksi.p90[yi].toFixed(1)}`} />
        </div>
        <FanChart {...props} title="Injury collisions avoided" unit="per year" band={s.injury} color={TEAL} />
        <FanChart {...props} title="Fatal or serious collisions avoided" unit="per year" band={s.ksi} color={TEAL} format={(v) => v.toFixed(v < 10 ? 1 : 0)} />
        {at('injury') >= 0.5 && (
          <>
            <RankList title="Most collisions avoided" unit="per year" rows={top(sc.hoodAvoided, yi, names.hoods)} color={TEAL} format={(v) => v.toFixed(1)} />
            <Scale label="Map: injury collisions avoided a year" from="#104648" to="#46f0dc" max={peakOf(sc.hoodAvoided, yi).toFixed(1)} />
          </>
        )}
        <p className="note">Dots are the {fmt(25378)} injury collisions of 2023 to 2025, with pedestrian and cyclist collisions in yellow. Waymo's US crash rate is raised 1.5× because it is unproven in Toronto's winters.</p>
      </>
    )
  }
  const live = at('waymoTrips') >= 1
  return (
    <>
      <h2>CO₂</h2>
      <p className="lede">
        {live
          ? "The net effect is close to zero, and its sign is uncertain. Waymos run on a clean grid but drive more empty km, and Toronto's bylaw already requires Uber and Lyft cars to go electric by 2031."
          : 'No change yet. Move the year forward to see the effect.'}
      </p>
      <div className="tiles">
        <Tile value={`${at('co2') > 0 ? '+' : ''}${fmt(at('co2'))} t`} label={`net CO₂e in ${year}`} note={span('co2')} />
        <Tile value={`${at('netKm') > 0 ? '+' : ''}${fmt(at('netKm'))}`} label="net km driven per day" note={`${((at('netKm') / 69.76e6) * 100).toFixed(2)}% of city driving`} />
      </div>
      <FanChart {...props} title="Net CO₂e" unit="tonnes a year, above zero is worse" band={s.co2} color={TEAL} />
      <PartsChart title="Where the 2035 figure comes from" unit="tonnes a year" rows={sc.co2Parts} />
      <Tornado title="What moves 2035 most" unit="tonnes, one input at a time" rows={sc.tornado.slice(0, 5)} />
      <p className="note">Each bar changes one input and starts from the ZEV rule holding, so bars centre above the headline median. Excludes building the cars.</p>
    </>
  )
})

export default function App() {
  const [model, setModel] = useState<Model | null>(null)
  const [day, setDay] = useState<TripDay | null>(null)
  const [wards, setWards] = useState<{ features: Feature[] } | null>(null)
  const [hoods, setHoods] = useState<{ features: Feature[] } | null>(null)
  const [dots, setDots] = useState<[number, number, number][]>([])
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<View>((params.get('view') as View) ?? 'streets')
  const [scenario, setScenario] = useState<ScenarioId>((params.get('scenario') as ScenarioId) ?? 'base')
  const [year, setYear] = useState(Number(params.get('year')) || 2035)
  const [minute, setMinute] = useState(START_MIN)
  const [playing, setPlaying] = useState(!params.has('paused'))
  const [speed, setSpeed] = useState(15)
  const [method, setMethod] = useState(params.has('method'))
  const frame = useRef(0)

  useEffect(() => {
    const json = (u: string) => fetch(u).then((r) => r.json())
    loadModel().then(setModel, (e: Error) => setError(e.message))
    loadTrips().then(setDay, (e: Error) => setError(e.message))
    json('/data/wards.geojson').then(setWards)
    json('/data/hoods.geojson').then(setHoods)
    json('/data/collisions.json').then(setDots)
  }, [])

  useEffect(() => {
    if (!playing || !day) return
    let last = performance.now()
    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.1)
      last = now
      setMinute((m) => (m + dt * speed) % MINUTES)
      frame.current = requestAnimationFrame(tick)
    }
    frame.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame.current)
  }, [playing, speed, day])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !(e.target instanceof HTMLButtonElement)) {
        e.preventDefault()
        setPlaying((p) => !p)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const onSeek = useCallback((m: number) => setMinute(m), [])
  const sc = model?.scenarios[scenario]
  const yi = model ? model.years.indexOf(year) : 0

  // A trip is a Waymo trip if both ends are in the open zone and its fixed draw is under this year's share.
  const split = useMemo(() => {
    if (!day || !sc) return null
    const share = sc.inZone[yi] / 100
    const isWaymo = (t: Trip) => {
      const a = sc.wardOpen[t.origin]
      const b = sc.wardOpen[t.dest]
      return a !== undefined && b !== undefined && a <= year && b <= year && t.draw < share
    }
    const waymo: Trip[] = []
    const human: Trip[] = []
    for (const t of day.trips) (isWaymo(t) ? waymo : human).push(t)
    return { waymo, human, curve: activeByMinute(waymo, () => true), all: activeByMinute(day.trips, () => true) }
  }, [day, sc, year, yi])

  const names = useMemo<Names>(() => {
    const pick = (fc: { features: Feature[] } | null, k: string) => Object.fromEntries((fc?.features ?? []).map((f) => [String(f.properties[k]), String(f.properties.name)]))
    return { wards: pick(wards, 'ward'), hoods: pick(hoods, 'hood') }
  }, [wards, hoods])

  const growth = model && sc ? sc.series.baseline.p50[yi] / model.evidence.market.ttm : 1
  const movingNow = split && day ? Math.round((split.curve[Math.floor(minute)] * day.sample * growth) / 10) * 10 : 0

  const layers = useMemo(() => {
    if (!sc || !split) return []
    if (view === 'drivers') {
      const peak = Math.max(1, peakOf(sc.wardDisplaced, yi))
      const val = (w: number | string) => sc.wardDisplaced[w]?.[yi] ?? 0
      return wards
        ? [
            new GeoJsonLayer({
              id: 'wards-disp',
              data: wards as never,
              pickable: true,
              getFillColor: (f: Feature) => {
                const v = val(f.properties.ward) / peak
                return v > 0 ? [...lerp([120, 72, 30], [250, 170, 80], Math.sqrt(v)), 150] : [255, 255, 255, 10]
              },
              getLineColor: [255, 255, 255, 60],
              lineWidthMinPixels: 1,
              updateTriggers: { getFillColor: [scenario, year] },
            }),
            new ColumnLayer<Feature>({
              id: 'ward-cols',
              data: wards.features.filter((f) => val(f.properties.ward) > 0),
              diskResolution: 24,
              radius: 620,
              extruded: true,
              pickable: true,
              getPosition: (f) => [Number(f.properties.lon), Number(f.properties.lat)],
              getElevation: (f) => val(f.properties.ward) * 0.8,
              getFillColor: [250, 170, 80, 235],
              updateTriggers: { getElevation: [scenario, year] },
            }),
          ]
        : []
    }
    if (view === 'safety') {
      const peak = Math.max(0.01, peakOf(sc.hoodAvoided, yi))
      return [
        hoods &&
          new GeoJsonLayer({
            id: 'hoods',
            data: hoods as never,
            pickable: true,
            getFillColor: (f: Feature) => {
              const v = (sc.hoodAvoided[f.properties.hood]?.[yi] ?? 0) / peak
              return v > 0 ? [...lerp([16, 70, 72], [70, 240, 220], v), 175] : [255, 255, 255, 8]
            },
            getLineColor: [255, 255, 255, 30],
            lineWidthMinPixels: 0.5,
            updateTriggers: { getFillColor: [scenario, year] },
          }),
        new ScatterplotLayer<[number, number, number]>({
          id: 'dots',
          data: dots,
          getPosition: (d) => [d[0], d[1]],
          getFillColor: (d) => (d[2] ? [255, 210, 120, 120] : [255, 255, 255, 46]),
          getRadius: 26,
          radiusMinPixels: 0.7,
        }),
      ]
    }
    const open = (f: Feature) => {
      const y = sc.wardOpen[f.properties.ward]
      return y !== undefined && y <= year
    }
    return [
      wards &&
        new GeoJsonLayer({
          id: 'zone',
          data: wards as never,
          getFillColor: (f: Feature) => (open(f) ? [60, 232, 212, 20] : [0, 0, 0, 0]),
          getLineColor: (f: Feature) => (open(f) ? [60, 232, 212, 80] : [255, 255, 255, 16]),
          lineWidthMinPixels: 1,
          updateTriggers: { getFillColor: [scenario, year], getLineColor: [scenario, year] },
        }),
      new TripsLayer<Trip>({
        id: 'human',
        data: split.human,
        getPath: (d) => d.path as never,
        positionFormat: 'XY',
        _pathType: 'open',
        getTimestamps: (d) => d.timestamps as never,
        getColor: HUMAN,
        currentTime: minute,
        trailLength: TRAIL,
        fadeTrail: true,
        widthMinPixels: 1.6,
        opacity: 0.75,
      }),
      new TripsLayer<Trip>({
        id: 'waymo',
        data: split.waymo,
        getPath: (d) => d.path as never,
        positionFormat: 'XY',
        _pathType: 'open',
        getTimestamps: (d) => d.timestamps as never,
        getColor: WAYMO,
        currentTime: minute,
        trailLength: TRAIL,
        fadeTrail: true,
        widthMinPixels: 1.8,
        capRounded: true,
        jointRounded: true,
        opacity: 0.95,
      }),
    ]
  }, [view, sc, split, wards, hoods, dots, minute, scenario, year, yi])

  const tooltip = useCallback(
    ({ object }: { object?: Feature }) => {
      if (!object || !sc) return null
      const p = object.properties
      const text =
        view === 'drivers'
          ? `${p.name}\n${fmt(sc.wardDisplaced[p.ward]?.[yi] ?? 0)} trips a day displaced in ${year}`
          : `${p.name}\n${(sc.hoodAvoided[p.hood]?.[yi] ?? 0).toFixed(1)} injury collisions avoided in ${year}`
      return { text, style: { background: '#10141c', color: '#e8ecf2', fontSize: '12px', borderRadius: '6px', border: '1px solid rgba(255,255,255,.14)' } }
    },
    [view, sc, yi, year],
  )

  return (
    <div className="app">
      <DeckGL initialViewState={INITIAL_VIEW} controller layers={layers} getTooltip={tooltip as never}>
        <BaseMap mapStyle={BASEMAP} attributionControl={false} />
      </DeckGL>

      <header className="panel title">
        <h1>Waymo in Toronto</h1>
        <p className="muted">A data forecast to 2040. Waymo plans first riders in 2028.</p>
        <nav className="segmented" aria-label="View">
          {VIEWS.map((v) => (
            <button key={v.id} className={v.id === view ? 'on' : ''} onClick={() => setView(v.id)}>
              {v.label}
            </button>
          ))}
          <button onClick={() => setMethod(true)}>Method</button>
        </nav>
      </header>

      {!(model && day) && <div className="panel loading">{error ?? 'Loading trips…'}</div>}

      {model && sc && (
        <aside className="panel side">
          <Panel view={view} model={model} sc={sc} year={year} names={names} />
        </aside>
      )}

      {model && sc && day && split && (
        <footer className="panel controls">
          <div className="year-row">
            <div className="year-big">{year}</div>
            <input
              type="range"
              min={model.years[0]}
              max={model.years[model.years.length - 1]}
              value={year}
              aria-label="Forecast year"
              onChange={(e) => setYear(Number(e.target.value))}
            />
            <div className="segmented" role="group" aria-label="Scenario">
              {SCENARIOS.map((id) => (
                <button key={id} className={id === scenario ? 'on' : ''} title={model.scenarios[id].summary} onClick={() => setScenario(id)}>
                  {model.scenarios[id].label}
                </button>
              ))}
            </div>
          </div>
          {(view === 'streets' || view === 'climate') && (
            <div className="day-row">
              <div className="readout">
                <div className="clock">{clock(minute)}</div>
                <div className="moving">
                  <strong>{movingNow.toLocaleString('en-US')}</strong> Waymos with riders
                </div>
              </div>
              <div className="day-main">
                <div className="buttons">
                  <button className="play" onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'Pause' : 'Play'}>
                    {playing ? '❚❚' : '▶'}
                  </button>
                  <div className="segmented" role="group" aria-label="Speed">
                    {SPEEDS.map((s) => (
                      <button key={s.value} className={s.value === speed ? 'on' : ''} onClick={() => setSpeed(s.value)}>
                        {s.label}
                      </button>
                    ))}
                  </div>
                  <ul className="legend">
                    <li>
                      <i style={{ background: `rgb(${WAYMO.join(',')})` }} />
                      Waymo
                    </li>
                    <li>
                      <i style={{ background: `rgb(${HUMAN.join(',')})` }} />
                      Uber and Lyft
                    </li>
                  </ul>
                </div>
                <DayTimeline active={split.all} waymo={split.curve} minute={minute} onSeek={onSeek} />
              </div>
            </div>
          )}
          <p className="footnote">
            {sc.summary} Forecast, not a measurement. Each line is {day.sample} real trips from a typical Friday (Jul 2025 to Jul 2026); ward, hour and duration are real, street addresses are synthetic. Data: City of Toronto, CPUC, Waymo. Basemap © CARTO, © OpenStreetMap contributors.
          </p>
        </footer>
      )}

      {method && model && <Method model={model} onClose={() => setMethod(false)} />}
    </div>
  )
}
