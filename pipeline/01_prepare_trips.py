"""Aggregate the City of Toronto PTC trip files (2018-2026) into small tables.

Input : data/raw/ptc/trips_YYYY.zip  (hourly ward-to-ward completed trips)
Output: data/interim/*.parquet
"""
import glob, zipfile
import numpy as np, pandas as pd

hourly, wardmonth, od = [], [], []
cols = ['pickup_hr','pickup_municipality','pickup_ward','dropoff_municipality','dropoff_ward',
        'trips_total','fare_avg','waittime_avg','distance_avg','duration_avg']
for z in sorted(glob.glob('data/raw/ptc/trips_20*.zip')):
    zf = zipfile.ZipFile(z)
    for n in sorted(zf.namelist()):
        if not n.endswith('.csv'): continue
        d = pd.read_csv(zf.open(n), usecols=lambda c: c in cols, low_memory=False)
        d.columns = [c.lower() for c in d.columns]
        # Timestamps carry a -04/-05 offset. Keep local wall-clock time.
        d['ts'] = pd.to_datetime(d['pickup_hr'].str.slice(0, 19))
        for c in ['fare_avg','waittime_avg','distance_avg','duration_avg']:
            d[c] = pd.to_numeric(d[c], errors='coerce')
        t = d['trips_total']
        for c in ['fare','waittime','distance','duration']:
            d[c+'_x'] = d[c+'_avg'] * t
        d['o'] = np.where(d.pickup_municipality.eq('Toronto'), d.pickup_ward, d.pickup_municipality)
        d['d'] = np.where(d.dropoff_municipality.eq('Toronto'), d.dropoff_ward, d.dropoff_municipality)
        agg = dict(trips=('trips_total','sum'), fare=('fare_x','sum'), wait=('waittime_x','sum'),
                   dist=('distance_x','sum'), dur=('duration_x','sum'))
        hourly.append(d.groupby('ts').agg(**agg).reset_index())
        d['month'] = d.ts.dt.to_period('M').astype(str)
        wardmonth.append(d.groupby(['month','o']).agg(**agg).reset_index())
        if d.ts.min() >= pd.Timestamp('2025-07-01'):
            d['dow'] = d.ts.dt.dayofweek; d['hour'] = d.ts.dt.hour
            od.append(d.groupby(['o','d','dow','hour']).agg(**agg).reset_index())
        print(n, len(d), int(t.sum()), flush=True)

pd.concat(hourly).groupby('ts').sum().reset_index().to_parquet('data/interim/hourly.parquet')
pd.concat(wardmonth).groupby(['month','o']).sum().reset_index().to_parquet('data/interim/ward_month.parquet')
pd.concat(od).groupby(['o','d','dow','hour']).sum().reset_index().to_parquet('data/interim/od_recent.parquet')
