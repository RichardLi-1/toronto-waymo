"""Neighbourhood x month x time-block injury-collision model (LightGBM, Poisson).
Validation: temporal holdout (2024-25) and leave-neighbourhoods-out spatial CV."""
import json, warnings
import numpy as np, pandas as pd, lightgbm as lgb, shap
from sklearn.model_selection import GroupKFold
warnings.filterwarnings('ignore')
c=pd.read_csv('data/raw/collisions/traffic_collisions.csv',low_memory=False,usecols=['OCC_YEAR','OCC_MONTH','OCC_DOW','OCC_HOUR','FATALITIES','INJURY_COLLISIONS','HOOD_158','PEDESTRIAN','BICYCLE','MOTORCYCLE'])
c=c[c.OCC_YEAR.between(2014,2025)]
c['inj']=(c.INJURY_COLLISIONS.eq('YES')|(c.FATALITIES.fillna(0)>0)).astype(int)
nsa_share=float((c[c.inj==1].HOOD_158=='NSA').mean())
c=c[(c.inj==1)&(c.HOOD_158!='NSA')].copy(); c['hood']=c.HOOD_158.astype(int)
mon={m:i+1 for i,m in enumerate('January February March April May June July August September October November December'.split())}
c['month']=c.OCC_MONTH.map(mon); c['wk']=c.OCC_DOW.isin(['Saturday','Sunday']).astype(int); c['blk']=(c.OCC_HOUR//4).astype(int)
g=c.groupby(['hood','OCC_YEAR','month','wk','blk']).size().rename('n').reset_index().rename(columns={'OCC_YEAR':'year'})
hf=pd.read_parquet('data/interim/hood_features.parquet')
idx=pd.MultiIndex.from_product([hf.hood,range(2014,2026),range(1,13),[0,1],range(6)],names=['hood','year','month','wk','blk']).to_frame(index=False)
d=idx.merge(g,how='left').fillna({'n':0}).merge(hf.drop(columns=['name','ward_name']),on='hood')
w=pd.DataFrame(json.load(open('data/raw/weather_yyz.json'))['hourly']); w['ts']=pd.to_datetime(w.time)
mw=w.groupby([w.ts.dt.year.rename('year'),w.ts.dt.month.rename('month')]).agg(snow=('snowfall','sum'),rain=('precipitation','sum'),temp=('temperature_2m','mean')).reset_index()
d=d.merge(mw,how='left',on=['year','month']); d[['snow','rain','temp']]=d.groupby('month')[['snow','rain','temp']].transform(lambda s:s.fillna(s.mean()))
d['covid']=d.year.isin([2020,2021]).astype(int)
for k in ['km_expressway','km_major','km_minor','km_collector','km_local']: d['l_'+k]=np.log1p(d[k])
F=['month','wk','blk','year','covid','snow','rain','temp','km2','pop','density','income','car_sh','transit_sh','walk_sh','bike_sh','age65_sh','age0_sh','l_km_expressway','l_km_major','l_km_minor','l_km_collector','l_km_local']
P=dict(objective='poisson',n_estimators=500,learning_rate=.04,num_leaves=47,min_child_samples=80,subsample=.8,subsample_freq=1,colsample_bytree=.7,reg_lambda=2,verbose=-1)
def dev(y,m):
    m=np.clip(m,1e-6,None); return 2*np.mean(np.where(y>0,y*np.log(np.where(y>0,y,1)/m),0)-(y-m))
out={}
tr=d[d.year<=2023]; te=d[d.year>=2024]
m=lgb.LGBMRegressor(**P).fit(tr[F],tr.n); p=m.predict(te[F])
# Fair baselines: (1) each neighbourhood x time-cell mean from training, (2) a single citywide mean per time cell.
b1=tr[tr.year>=2022].groupby(['hood','wk','blk']).n.mean().rename('b').reset_index(); bb=te.merge(b1,on=['hood','wk','blk'],how='left').b.values
null=dev(te.n.values,np.full(len(te),te.n.mean()))
out['temporal']=dict(d2_model=1-dev(te.n.values,p)/null,d2_hood_history=1-dev(te.n.values,bb)/null,total_pred=float(p.sum()),total_actual=float(te.n.sum()))
# Annual neighbourhood totals: the level at which the map is read.
a=te.assign(p=p,b=bb).groupby('hood')[['n','p','b']].sum()
out['temporal']['hood_annual_r2_model']=float(np.corrcoef(a.n,a.p)[0,1]**2); out['temporal']['hood_annual_mape_model']=float((np.abs(a.n-a.p)/a.n.clip(lower=1)).median()); out['temporal']['hood_annual_mape_history']=float((np.abs(a.n-a.b)/a.n.clip(lower=1)).median())
pr=np.zeros(len(d))
for a_,b_ in GroupKFold(5).split(d,groups=d.hood):
    k=lgb.LGBMRegressor(**{**P,'n_estimators':300}).fit(d.iloc[a_][F],d.iloc[a_].n); pr[b_]=k.predict(d.iloc[b_][F])
nu=dev(d.n.values,np.full(len(d),d.n.mean()))
s=d.assign(p=pr).groupby('hood')[['n','p']].sum()
out['spatial']=dict(d2=1-dev(d.n.values,pr)/nu,hood_r2=float(np.corrcoef(s.n,s.p)[0,1]**2),hood_mape=float((np.abs(s.n-s.p)/s.n).median()))
print(json.dumps(out,indent=1))
fin=lgb.LGBMRegressor(**P).fit(d[F],d.n)
sm=d.sample(5000,random_state=2); sv=shap.TreeExplainer(fin).shap_values(sm[F]); imp=pd.Series(np.abs(sv).mean(0),F).sort_values(ascending=False); print(imp.round(3).head(12).to_string())
out['importance']=imp.round(4).head(10).to_dict(); out['nsa_share']=nsa_share
# Expected injury collisions at 2025 conditions, typical weather.
q=d[d.year==2025].copy(); q['p']=fin.predict(q[F]); e=q.groupby('hood').agg(expected=('p','sum'),actual=('n','sum'))
h3=d[d.year.isin([2023,2024,2025])].groupby('hood').n.sum()/3
e['obs3']=h3; e.to_parquet('data/interim/hood_collisions.parquet'); print(e.sum().round(0).to_dict())
tb=q.groupby(['wk','blk']).p.sum(); out['time_block']={f'{a}-{b}':float(v) for (a,b),v in tb.items()}
json.dump(out,open('data/interim/collision_model.json','w'),indent=1)
