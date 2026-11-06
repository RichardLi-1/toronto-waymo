# Waymo in Toronto: research notes

As of 2026-11-06. Figures labelled "forecast" come from this project's model. Everything else is sourced or measured.

## Where things stand

- Waymo [announced Toronto on October 16, 2026](https://techcrunch.com/2026/10/16/waymos-robotaxis-are-headed-to-canada/) and is [targeting first riders in 2028](https://electrek.co/2026/10/16/waymo-toronto-canada-robotaxi-2028/). Element Fleet Management will run the fleet.
- Fleet size and service area have not been announced.
- Ontario's automated vehicle rule, O. Reg. 306/15, [is revoked on October 13, 2027](https://electrek.co/2026/10/16/waymo-toronto-canada-robotaxi-2028/), and it covers testing, not paid service. No replacement has been announced, so this is the biggest risk to the date.
- Mayor Chow's office [says she won't support Waymo if it costs jobs](https://www.cp24.com/local/toronto/2026/04/13/could-self-driving-rideshare-vehicles-be-coming-to-toronto-one-california-based-company-wants-a-shot-at-it/). Regulation sits with the province.

## Forecast results

Medians, with P10 to P90 in brackets where shown.

| 2035 | Slow | Base | Fast |
| --- | --- | --- | --- |
| Median launch | Jun 2030 | Dec 2028 | Jun 2028 |
| Fleet | 1,035 | 3,397 (2,356 to 4,969) | 9,350 |
| Waymo trips a day | 18,500 | 60,600 | 166,600 |
| Share of ride-hail trips | 4.4% | 14.1% (11.1% to 17.3%) | 36.0% |
| Uber and Lyft trips a day | 396,700 | 366,800 | 295,700 |
| Same, with no Waymo | 409,800 | 407,900 | 411,200 |
| Driver jobs displaced (full-time equivalent) | 1,300 | 4,200 (3,000 to 6,100) | 11,600 |
| Fares moved to Waymo a year | $92M | $301M | $827M |
| Injury collisions avoided a year | 35 | 116 (62 to 191) | 321 |
| Fatal or serious collisions avoided a year | 1.4 | 4.7 (2.8 to 7.3) | 12.8 |
| Net km driven a day | +106,000 | +347,000 | +977,000 |
| Net CO₂e a year | +480 t | +1,500 t (-25,000 to +21,000) | +4,900 t |

### What it means

1. **Drivers lose growth, not today's volume.** In every scenario, Uber and Lyft trips stay above the 2026 level. The harm is trips drivers would otherwise have had. This depends on the market continuing to grow, which is an extrapolation.
2. **The safety gain is real but small.** Ride-hailing is about 4.5% of driving in Toronto, so even a far safer driver moves citywide injury collisions by only about 1.2% in the base case.
3. **CO₂ is a coin flip.** There's a 54% chance net emissions rise in 2035. If Toronto's ZEV bylaw holds, base-case net is about +8,600 t. If it lapses, about -14,600 t.
4. **Total driving rises.** Waymo drives about 42% of its km empty in California, against about 30% recorded for Toronto ride-hail, and some riders come from transit and walking.

## What the data showed

- **Market:** Toronto had [87.1M ride-hail trips in 2025](https://findingspress.org/article/164827-how-much-ridehail-travel-is-deadheading-estimating-its-share-and-evolution-in-toronto), equal to 21% of TTC ridership. This project's own count is 87,068,044. Growth is slowing, from about 21% a year in 2024 to about 12% in mid-2026.
- **Waymo's plateau:** California trips levelled off at about 45,000 a day in 2026, from [CPUC filings](https://www.cpuc.ca.gov/regulatory-services/licensing/transportation-licensing-and-analysis-branch/autonomous-vehicle-programs/quarterly-reporting). It could be demand, or cars moved to new cities. Public data can't separate them, and the base case leans on this.
- **Share in US cities:** [Yipit puts Waymo at 15% to 16% of spending](https://finance.yahoo.com/technology/articles/waymo-eating-ride-hailing-market-071101387.html) in its San Francisco, Los Angeles and Phoenix zones in June 2026. Earlier readings were [20% to 27%](https://www.thedriverlessdigest.com/p/15-charts-that-explain-the-autonomous), though zones have grown since.
- **Snow:** the expected demand surge didn't appear. With 10 cm or more in 24 hours, demand falls about 14% and waits rise about 50%. Snowy hours hold about 6% of annual trips.
- **2026 supply squeeze:** active vehicles fell from about 36,600 to 33,400 while trips grew, and waits rose from 4 to 6 minutes. "Available" km also dropped sharply. The cause isn't known and part of it may be a reporting change.
- **Safety record:** [Waymo's hub](https://waymo.com/safety/impact/), through June 2026, reports 271.3M rider-only miles, 82% fewer injury crashes and 95% fewer serious-injury crashes. The serious-injury figure rests on 3 Waymo events, and no winter city is in the data.
- **Driver earnings:** in Los Angeles, [Gridwise found driver hours down 17.8% and quarterly pay down 14.7%](https://laist.com/news/transportation/waymo-economics-la-uber-lyft-drivers-report-gridwise) from Q2 2024 to Q2 2026. That is a before-and-after comparison, not proof of cause, and it's larger than this model would imply at a similar share.

## Model checks

| Model | Test | Result | Baseline |
| --- | --- | --- | --- |
| Toronto market | Predict the 12 months after Jul 2025 | 2.2% error | -11.7% (no growth) |
| Hourly demand with weather | 12 rolling monthly folds | 6.9% WAPE | 9.3% (same hour last week) |
| Waymo ramp | Predict the next 6 months | 16.8% median error | 20.8% (Gompertz) |
| Collisions, future years | Train to 2023, test 2024 to 2025 | R² 0.94 by neighbourhood | 26% vs 18% median error |
| Collisions, unseen neighbourhoods | 5-fold grouped CV | R² 0.67 | n/a |

Backtests test the pieces, not the forecast. No city has been through this transition under Toronto's conditions, so the 2035 numbers can't be validated.

## Weakest inputs

These are judgment calls or thin evidence. Change these first if better data appears.

- **What Waymo trips replace (55% to 85% from Uber and Lyft).** No published figure exists. [Waymo told the London Assembly](https://gla.moderngov.co.uk/documents/s123329/Appendix%204%20Annex%20a%20-%20Appendix%202_Waymos%20response%20to%20the%20additional%20questions_July%202026.pdf) the alternative mode isn't directly observable.
- **Launch dates and the Fast share ceiling.** These are scenario choices, not estimates.
- **Waymo energy use (0.32 to 0.46 kWh/km).** There's no measured Ojai figure, and the I-Pace estimate is low confidence.
- **Toronto fleet mix.** The latest Toronto data is from 2023 ([about 82% gas, 15% hybrid, 3% plug-in](https://www.toronto.ca/legdocs/mmis/2023/ec/bgrd/backgroundfile-239119.pdf)). The 8% electric figure for 2026 is an assumption.
- **ZEV bylaw holds (60%).** [§546-13.9](https://www.toronto.ca/legdocs/municode/toronto-code-546.pdf) is enacted, but the copy reviewed is a June 2024 consolidation. No delay was found through about May 2026.
- **Winter crash penalty (1.5×).** No data exists yet.
- **Neighbourhood collision rankings.** These use a road-class traffic proxy and synthetic trip locations. Trust the broad pattern only.

## Data

| Dataset | Used for |
| --- | --- |
| [Toronto PTC trips and summary](https://open.toronto.ca/dataset/private-transportation-companies-summary-and-trip-data/) | Hourly ward-to-ward trips, fares, waits, vehicles, 2018 to Jul 2026 |
| [CPUC AV quarterly reports](https://www.cpuc.ca.gov/regulatory-services/licensing/transportation-licensing-and-analysis-branch/autonomous-vehicle-programs/quarterly-reporting) | Waymo monthly trips and miles. Trip-level and tract fields are redacted |
| [avrideshare tracker](https://avrideshare.platformaeronaut.com/tracker/california/operators/waymo) | 2023 to 2024 months, republished from CPUC. Secondary source |
| [Waymo Safety Impact Hub](https://waymo.com/safety/impact/) | Crash ratios by road user |
| [Toronto Police traffic collisions](https://open.toronto.ca/dataset/police-annual-statistical-report-traffic-collisions/) | 825,000 collisions, 2014 to 2026 |
| [KSI collisions](https://open.toronto.ca/dataset/motor-vehicle-collisions-involving-killed-or-seriously-injured-persons/) | Fatal and serious collisions |
| [Vehicle-for-hire review, 2024](https://www.toronto.ca/legdocs/mmis/2024/ex/bgrd/backgroundfile-251488.pdf) | 69.76M km a day of total driving, mode substitution |
| [TAF emissions factors, 2025](https://taf.ca/custom/uploads/2025/10/2025TAF-EmissionsFactors.pdf) | Ontario grid intensity to 2040 |
| [Neighbourhood profiles](https://open.toronto.ca/dataset/neighbourhood-profiles/) | 2021 census features |
| [Open-Meteo archive](https://open-meteo.com/) | Hourly Toronto weather |
| OpenStreetMap | Street network |
