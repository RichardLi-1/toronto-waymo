"""Hourly citywide demand model: calendar + weather -> ride-hail trips and waits.
Target is the ratio to a same-hour-of-week baseline lagged 14+ days, so the model
isolates weather and calendar effects without leaking the trend.
Validation: rolling-origin over the last 12 months, against seasonal-naive."""
import json, warnings
import numpy as np, pandas as pd, lightgbm as lgb, shap
warnings.filterwarnings('ignore')
h=pd.read_parquet('data/interim/hourly.parquet')
w=pd.DataFrame(json.load(open('data/raw/weather_yyz.json'))['hourly']); w['ts']=pd.to_datetime(w.time); w=w.drop(columns='time')
d=h.merge(w,on='ts').sort_values('ts')
d=d[d.ts>='2022-06-01'].copy()
d['wait']=d.wait/d.trips
d['how']=d.ts.dt.day_of_week*24+d.ts.dt.hour
# Baseline: mean of the same hour-of-week 2-5 weeks earlier.
for col in ['trips','wait']:
    g=d.groupby('how')[col]
    d[col+'_base']=(g.shift(2)+g.shift(3)+g.shift(4)+g.shift(5))/4
d=d.dropna(subset=['trips_base'])
d['hour']=d.ts.dt.hour; d['dow']=d.ts.dt.day_of_week; d['doy']=d.ts.dt.day_of_year; d['month']=d.ts.dt.month
d['snow6']=d.snowfall.rolling(6,min_periods=1).sum(); d['snow24']=d.snowfall.rolling(24,min_periods=1).sum()
d['rain3']=d.precipitation.rolling(3,min_periods=1).sum()
hol=pd.to_datetime(['2023-01-02','2023-02-20','2023-04-07','2023-05-22','2023-07-03','2023-08-07','2023-09-04','2023-10-09','2023-12-25','2023-12-26','2024-01-01','2024-02-19','2024-03-29','2024-05-20','2024-07-01','2024-08-05','2024-09-02','2024-10-14','2024-12-25','2024-12-26','2025-01-01','2025-02-17','2025-04-18','2025-05-19','2025-07-01','2025-08-04','2025-09-01','2025-10-13','2025-12-25','2025-12-26','2026-01-01','2026-02-16','2026-04-03','2026-05-18','2026-07-01'])
d['holiday']=d.ts.dt.normalize().isin(hol).astype(int)
F=['hour','dow','doy','month','holiday','temperature_2m','precipitation','rain3','snowfall','snow6','snow24','snow_depth']
d['y']=np.log(d.trips.clip(lower=1)/d.trips_base.clip(lower=1)); d['yw']=np.log(d.wait.clip(lower=.5)/d.wait_base.clip(lower=.5))
P=dict(objective='regression',n_estimators=500,learning_rate=.03,num_leaves=31,min_child_samples=40,subsample=.8,subsample_freq=1,colsample_bytree=.8,verbose=-1)
folds=pd.date_range('2025-08-01','2026-07-01',freq='MS'); preds=[]
for s,e in zip(folds[:-1],folds[1:]):
    tr=d[d.ts<s-pd.Timedelta(days=1)]; te=d[(d.ts>=s)&(d.ts<e)]
    m=lgb.LGBMRegressor(**P).fit(tr[F],tr.y); preds.append(te.assign(p=m.predict(te[F])))
b=pd.concat(preds); b['pred']=b.trips_base*np.exp(b.p)
b['naive']=b.groupby('how').trips.shift(1)
b=b.dropna(subset=['naive'])
wape=lambda a,f:float(np.abs(a-f).sum()/a.sum())
r=dict(model_wape=wape(b.trips,b.pred),baseline4wk_wape=wape(b.trips,b.trips_base),naive_week_wape=wape(b.trips,b.naive),n_hours=len(b))
snow=b[b.snow24>=5]; r['snow_model_wape']=wape(snow.trips,snow.pred); r['snow_base_wape']=wape(snow.trips,snow.trips_base); r['snow_hours']=len(snow)
print(r)
m=lgb.LGBMRegressor(**P).fit(d[F],d.y); mw=lgb.LGBMRegressor(**P).fit(d[F],d.yw)
sample=d.sample(6000,random_state=1); sv=shap.TreeExplainer(m).shap_values(sample[F])
imp=pd.Series(np.abs(sv).mean(0),F).sort_values(ascending=False); print(imp.round(4).to_string())
# Partial effect: set weather to dry at the same hours, compare predictions on snowy hours.
def effect(model,mask):
    a=d[mask]; c=a.copy(); c[['snowfall','snow6','snow24']]=0
    return float(np.exp((model.predict(a[F])-model.predict(c[F])).mean())-1)
r['eff']={k:dict(hours=int(mk.sum()),demand=effect(m,mk),wait=effect(mw,mk)) for k,mk in {'snow24_1_5':(d.snow24>=1)&(d.snow24<5),'snow24_5_10':(d.snow24>=5)&(d.snow24<10),'snow24_10p':d.snow24>=10}.items()}
print(r['eff'])
# Winter exposure: share of annual trips in hours with active or recent snow.
dd=d[d.ts>='2023-01-01']; 
r['share_trips_snow24_ge1']=float(dd[dd.snow24>=1].trips.sum()/dd.trips.sum()); r['share_hours_snow24_ge1']=float((dd.snow24>=1).mean())
r['share_trips_snow24_ge5']=float(dd[dd.snow24>=5].trips.sum()/dd.trips.sum()); r['share_hours_snow24_ge5']=float((dd.snow24>=5).mean())
r['importance']=imp.round(5).to_dict()
print({k:round(v,4) for k,v in r.items() if k.startswith('share')})
json.dump(r,open('data/interim/demand_weather.json','w'),indent=1)
