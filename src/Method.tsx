import { EvidenceLine } from './charts'
import type { Model } from './model'

const pct = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`

const ASSUMPTIONS: [string, string, string, string][] = [
  ['Market growth decay', 'Fitted', 'Half-life from Toronto trips, 2023 to 2026', 'Toronto PTC data'],
  ['Ramp speed', 'Fitted', '0.195 a month, half of plateau at 14 to 24 months', 'CPUC monthly filings'],
  ['In-zone share ceiling', 'Sourced, then judged', '12% slow, 22% base, 45% fast', 'Yipit: 15% to 27% in US zones. Fast is a judgment'],
  ['Launch date', 'Judgment', 'Mid-2030, end of 2028, mid-2028', 'Ontario rule lapses Oct 2027 with no successor yet'],
  ['Trips replacing Uber/Lyft', 'Judgment', '55% to 85%', 'No published figure. Waymo says it cannot observe this'],
  ['Trips per car per day', 'Sourced, adjusted', '18 ± 2.5', 'About 20 in the US, lower for longer Toronto trips'],
  ['Crash ratio, injury', 'Sourced', '0.17 × 1.5 Toronto penalty', 'Waymo hub to June 2026. The penalty is a judgment'],
  ['Crash ratio, fatal or serious', 'Sourced, widened', '0.12 median', 'Only 3 Waymo events, so the interval is wide'],
  ['Waymo energy', 'Weak', '0.32 to 0.46 kWh/km at the wall', 'No measured Ojai figure exists'],
  ['Grid intensity', 'Sourced', 'Mix of average and marginal', 'TAF 2025 factors'],
  ['ZEV bylaw holds', 'Judgment', '60% chance', '§546-13.9 is law. Enforcement is the open question'],
  ['Current fleet mix', 'Weak', '8% electric in 2026', 'Latest Toronto data is 2023. Uber reports 9.1% for the US and Canada'],
]

const SOURCES: [string, string][] = [
  ['City of Toronto: PTC trips and summary data', 'https://open.toronto.ca/dataset/private-transportation-companies-summary-and-trip-data/'],
  ['CPUC: AV quarterly reporting', 'https://www.cpuc.ca.gov/regulatory-services/licensing/transportation-licensing-and-analysis-branch/autonomous-vehicle-programs/quarterly-reporting'],
  ['Waymo Safety Impact Hub', 'https://waymo.com/safety/impact/'],
  ['Toronto Police: traffic collisions', 'https://open.toronto.ca/dataset/police-annual-statistical-report-traffic-collisions/'],
  ['City of Toronto: vehicle-for-hire review, 2024', 'https://www.toronto.ca/legdocs/mmis/2024/ex/bgrd/backgroundfile-251488.pdf'],
  ['Toronto Municipal Code, Chapter 546', 'https://www.toronto.ca/legdocs/municode/toronto-code-546.pdf'],
  ['TAF: 2025 emissions factors', 'https://taf.ca/custom/uploads/2025/10/2025TAF-EmissionsFactors.pdf'],
  ['Young, Allen and Wang: deadheading in Toronto', 'https://findingspress.org/article/164827-how-much-ridehail-travel-is-deadheading-estimating-its-share-and-evolution-in-toronto'],
  ['Abdelhalim: Waymo empty miles in California', 'https://doi.org/10.32866/001c.161870'],
  ['Electrek: Waymo picks Toronto', 'https://electrek.co/2026/10/16/waymo-toronto-canada-robotaxi-2028/'],
]

export function Method({ model, onClose }: { model: Model; onClose: () => void }) {
  const e = model.evidence
  const t = e.collisions.temporal
  const sp = e.collisions.spatial
  const w = e.weather
  const r = e.ramp
  const m = e.market
  const from = m.months.indexOf('2022-01')
  return (
    <div className="method" role="dialog" aria-label="Method">
      <div className="method-body">
        <button className="close" onClick={onClose}>
          Back to the map
        </button>
        <h1>How this forecast works</h1>
        <p className="lede">Four models feed a Monte Carlo simulation of 4,000 runs per scenario. Bands on the charts run from P10 to P90. They show the spread from the inputs below, so the real uncertainty is wider.</p>

        <h2>What was tested</h2>
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>Test</th>
              <th>Result</th>
              <th>Baseline</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Toronto market growth</td>
              <td>Fit to Jul 2025, predict the next 12 months</td>
              <td>{pct(m.backtestErr)} error</td>
              <td>{pct(m.naiveErr)} (no growth)</td>
            </tr>
            <tr>
              <td>Hourly demand with weather (LightGBM)</td>
              <td>12 rolling monthly folds</td>
              <td>{pct(w.model_wape)} WAPE</td>
              <td>{pct(w.naive_week_wape)} (same hour last week)</td>
            </tr>
            <tr>
              <td>Same model, snowy hours only</td>
              <td>5 cm or more in 24 hours</td>
              <td>{pct(w.snow_model_wape)} WAPE</td>
              <td>{pct(w.snow_base_wape)} (4-week average)</td>
            </tr>
            <tr>
              <td>Waymo ramp (logistic)</td>
              <td>Fit to month k, predict the next 6</td>
              <td>{pct(r.holdout)} median error</td>
              <td>Gompertz: 20.8%</td>
            </tr>
            <tr>
              <td>Collisions by neighbourhood (LightGBM, Poisson)</td>
              <td>Train to 2023, test 2024 to 2025</td>
              <td>R² {t.hood_annual_r2_model.toFixed(2)}, {pct(t.hood_annual_mape_model, 0)} median error</td>
              <td>{pct(t.hood_annual_mape_history, 0)} (recent history)</td>
            </tr>
            <tr>
              <td>Same model, unseen neighbourhoods</td>
              <td>5-fold, grouped by neighbourhood</td>
              <td>R² {sp.hood_r2.toFixed(2)}, {pct(sp.hood_mape, 0)} median error</td>
              <td>n/a</td>
            </tr>
          </tbody>
        </table>
        <p className="note">The collision model under-predicted the 2024 to 2025 citywide total by {pct(1 - t.total_pred / t.total_actual, 0)}, because trees cannot extrapolate the post-COVID rebound. It is used only to say where risk sits. Citywide totals come from observed counts.</p>

        <div className="evidence">
          <EvidenceLine title="Waymo trips per day in California" unit="solid: filings, dashed: fit" labels={r.series.map((d: { m: string }) => d.m)} actual={r.series.map((d: { trips_day: number }) => d.trips_day)} fit={r.series.map((d: { fit: number }) => d.fit)} color="#14a899" />
          <EvidenceLine title="Toronto ride-hail trips per day" unit="monthly average" labels={m.months.slice(from)} actual={m.tripsDay.slice(from)} color="#d97512" />
        </div>

        <h2>What the data showed</h2>
        <ul>
          <li>California Waymo trips levelled off near {Math.round(r.K / 1000)}k a day in 2026. That may be demand, or cars sent to new cities. The public data can't separate the two.</li>
          <li>Heavy snow (10 cm or more in 24 hours) cuts demand {pct(-w.eff.snow24_10p.demand, 0)} and raises waits {pct(w.eff.snow24_10p.wait, 0)}. Snowy hours hold only {pct(w.share_trips_snow24_ge1, 0)} of annual trips, so winter is a reliability risk more than a volume one.</li>
          <li>Since late 2025, active vehicles fell about 10% while trips grew, waits rose from 4 to 6 minutes and recorded empty km dropped. The cause is unknown and may be partly a reporting change.</li>
          <li>Waymo drives 42% of its California km empty. Toronto ride-hail is near 30% on routed data, which likely understates cruising.</li>
        </ul>

        <h2>Inputs</h2>
        <table>
          <thead>
            <tr>
              <th>Input</th>
              <th>Basis</th>
              <th>Value</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {ASSUMPTIONS.map((a) => (
              <tr key={a[0]}>
                {a.map((c) => (
                  <td key={c}>{c}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>

        <h2>What this leaves out</h2>
        <ul>
          <li>Congestion from pickups and stopped cars, parking, transit revenue, and new Waymo jobs (the company says "hundreds").</li>
          <li>Embodied emissions from building the cars. No peer-reviewed g/km figure could be verified.</li>
          <li>Airport and cross-boundary trips, about 19% of the market. They are treated as never served.</li>
          <li>Reliable neighbourhood rankings. Traffic per neighbourhood is estimated from road class, and trip locations inside a ward are synthetic, so treat the Collisions map as a broad pattern. Ward-level and citywide figures don't depend on this.</li>
          <li>Other robotaxi operators. Share is uniform across open wards, and new wards get the mature share at once.</li>
        </ul>

        <h2>Sources</h2>
        <ul>
          {SOURCES.map(([label, url]) => (
            <li key={url}>
              <a href={url} target="_blank" rel="noreferrer">
                {label}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
