"""Monte Carlo forecast of Waymo in Toronto, 2026-2040, three scenarios.

Every input is tagged in docs/assumptions via the ASSUMPTIONS list below:
  fitted  = estimated in this repo from public data
  sourced = taken from a cited document
  judgment= no published value exists; a wide range chosen by hand
Writes public/data/model.json."""
import json, re, warnings
import numpy as np, pandas as pd, geopandas as gpd
warnings.filterwarnings('ignore')
rng=np.random.default_rng(2028)
N=4000
YEARS=np.arange(2026,2041)
T=2026+np.arange(15*12)/12+1/24            # monthly grid
ramp=json.load(open('data/interim/ramp_fit.json')); mk=json.load(open('data/interim/market_fit.json'))
dw=json.load(open('data/interim/demand_weather.json')); cm=json.load(open('data/interim/collision_model.json'))

# ---- Toronto data-derived constants
s=pd.read_csv('data/raw/ptc/summary_stats.csv',parse_dates=['dt']); t=s[s.dt>='2025-08-01']
MIN_APP=float((t.time_available+t.time_enroute+t.time_waiting+t.time_ontrip).sum()/t.reported_trips_started.sum())
FARE=float(np.average(t.fare_avg,weights=t.reported_trips_started)); KM=float(np.average(t.dist_avg,weights=t.reported_trips_started))
FTE_H_DAY=40*52/365
VKT_YEAR=69.7557e6*365                     # City of Toronto Fig 5-1, 2023, all vehicles
INJ_YEAR=(8599+10645+10010)/3              # Police traffic collisions, 2023-25, injury
KSI_YEAR=(334+296+256)/3                   # KSI collisions, 2023-25

# Exposure weighting: ride-hail km sit where collisions per km are higher than average.
hf=pd.read_parquet('data/interim/hood_features.parquet'); hk=pd.read_parquet('data/interim/hood_km.parquet'); hc=pd.read_parquet('data/interim/hood_collisions.parquet').reset_index()
h=hf.merge(hk,on='hood',how='left').merge(hc,on='hood').fillna({'km_day':0})
h['vkt']=h.vkt_w*(69.7557e6/h.vkt_w.sum())
h['rate']=h.expected/(h.vkt*365)
RATE_CITY=INJ_YEAR/VKT_YEAR
RH_MULT=float((h.km_day*h.rate).sum()/h.km_day.sum()/(h.expected.sum()/(h.vkt.sum()*365)))
print('ride-hail exposure multiplier',round(RH_MULT,2),'min/app',round(MIN_APP,1),'fare',round(FARE,2),'km',round(KM,2))

# ---- Crash ratio, reweighted to Toronto's road-user mix
d=pd.read_csv('data/raw/waymo/csv3.csv'); a=d[d['County Name'].str.startswith('All Loc')&(d['Benchmark Comparison']=='Any-injury-reported')].set_index('Conflict Partner Type Group')
vr=a.loc[['Pedestrian','Cyclist']]; vuln=vr['Waymo Count'].sum()/vr['Predicted Benchmark Count'].sum()
oth=(a.loc['All Crashes','Waymo Count']-vr['Waymo Count'].sum())/(a.loc['All Crashes','Predicted Benchmark Count']-vr['Predicted Benchmark Count'].sum())
RR_INJ=float(.233*vuln+.767*oth); print('RR injury, Toronto mix',round(RR_INJ,3),'vulnerable',round(vuln,3),'other',round(oth,3))

# ---- Service-area growth on the real origin-destination table
g=pd.read_parquet('data/interim/od_clean.parquet')
g=g[g.o2.str.fullmatch(r'\d+')&g.d2.str.fullmatch(r'\d+')].assign(o=lambda x:x.o2.astype(int),d=lambda x:x.d2.astype(int))
ALL=pd.read_parquet('data/interim/od_clean.parquet').trips.sum()
od=g.groupby(['o','d']).trips.sum()
W=gpd.read_file('public/data/wards.geojson').to_crs(26917); W['geometry']=W.buffer(60)
adj={r.ward:set(W[W.intersects(r.geometry)].ward)-{r.ward} for r in W.itertuples()}
area=dict(zip(W.ward,W.area/1e6)); pick=g.groupby('o').trips.sum()
order=[10,13,11]
while len(order)<25:
    c={x for w in order for x in adj[w]}-set(order)
    order.append(max(c,key=lambda x:pick[x]/area[x]))
cov=[]
for k in range(1,26):
    S=set(order[:k]); cov.append(od[od.index.get_level_values(0).isin(S)&od.index.get_level_values(1).isin(S)].sum()/ALL)
cov=np.array(cov); print('order',order); print('coverage',cov.round(3)[[2,5,9,14,19,24]])

# ---- Grid and fuels (TAF 2025 factors, g/kWh)
GY=[2025,2030,2035,2040]; AVG=[75,106,44,50]; MARG=[392,397,352,314]
avg=np.interp(T,GY,AVG); marg=np.interp(T,GY,MARG)

SC={
 'slow':dict(label='Slow',summary='Ontario takes until 2030 to legalise paid service. Waymo stays in the core.',launch=(2030.5,.5),ceil=(.08,.12,.18),pace=1.0,kmax=8),
 'base':dict(label='Base',summary='Service starts around the end of 2028 and reaches the share Waymo holds in US cities today.',launch=(2028.95,.4),ceil=(.15,.22,.30),pace=2.5,kmax=20),
 'fast':dict(label='Fast',summary='Waymo hits its 2028 target, fares reach Uber parity and it wins share well past today\'s US levels.',launch=(2028.5,.2),ceil=(.30,.45,.60),pace=5.0,kmax=25),
}
def tri(a,b,c,n): return rng.triangular(a,b,c,n)
def draw(sc,n=N):
    c=SC[sc]
    mix=rng.dirichlet(np.array([.45,.10,.25,.08,.12])*30,n)   # transit,taxi,auto,active,none
    return dict(
      launch=rng.normal(c['launch'][0],c['launch'][1],n), ceil=tri(*c['ceil'],n),
      r=rng.normal(ramp['logistic']['r'],.03,n).clip(.1,.3), t50=rng.uniform(14,24,n),
      pace=c['pace']*rng.uniform(.7,1.3,n), kmax=np.full(n,float(c['kmax'])),
      tau=rng.lognormal(np.log(mk['tau']),.3,n), ginf=rng.uniform(0,.015,n),
      pause=rng.uniform(.3,.9,n), tpv=rng.normal(18,2.5,n).clip(11,26),
      d=rng.uniform(.55,.85,n), transit=mix[:,0],taxi=mix[:,1],auto=mix[:,2],
      occ_w=rng.uniform(.52,.65,n), occ_u=rng.uniform(.62,.76,n),
      kwh_w=rng.uniform(.32,.46,n), kwh_e=rng.uniform(.19,.26,n), gridw=rng.uniform(0,1,n),
      e_gas=rng.uniform(230,300,n), e_hyb=rng.uniform(160,205,n), e_car=rng.uniform(250,330,n),
      zev=(rng.uniform(size=n)<.6).astype(float),
      rr_inj=np.minimum(RR_INJ*rng.lognormal(np.log(1.5),.35,n),1), rr_ksi=np.minimum(rng.lognormal(np.log(.12),.6,n),1),
      inv=rng.uniform(1,1.7,n), mult=np.full(n,RH_MULT))
def run(p):
    col=lambda k:p[k][:,None]
    x=T[None,:]
    # Market without Waymo: integrate the decaying growth rate from the trailing-12-month centre.
    g=col('ginf')+(mk['g0']-col('ginf'))*np.exp(-(x-2023.5)/col('tau'))
    M=mk['ttm_trips_day']*np.exp(np.cumsum(g/12,axis=1))
    tm=(x-col('launch'))*12
    live=tm>=0
    S=col('ceil')/(1+np.exp(-col('r')*(tm-col('t50'))))*live*(1-col('pause')*dw['share_trips_snow24_ge1'])
    k=np.minimum(3+col('pace')*np.maximum(x-col('launch'),0),col('kmax'))
    C=np.interp(k,np.arange(1,26),cov)*live
    Mz=M*C; dd=col('d')
    Wt=S*Mz/(1-S*(1-dd)); D=dd*Wt
    UL=M-D
    # Fleet mix of the human ride-hail fleet.
    bev0=.08+(.45-.08)*np.clip((x-2026)/14,0,1)
    rule=np.clip((x-2030)/1.0,0,1)
    bev=bev0*(1-col('zev'))+col('zev')*(bev0+(.9-bev0)*rule)
    hyb=(1-bev)*np.clip(.30+.02*(x-2026),0,.7)
    gas=1-bev-hyb
    grid=avg+(marg-avg)*col('gridw')
    e_u=gas*col('e_gas')+hyb*col('e_hyb')+bev*col('kwh_e')*grid
    kw=KM/col('occ_w'); ku=KM/col('occ_u')
    e_w=col('kwh_w')*grid
    other=Wt*(1-dd)
    car_km=other*col('auto')*KM; taxi_km=other*col('taxi')*ku
    co2_w=Wt*kw*e_w*365/1e6; co2_u=-D*ku*e_u*365/1e6; co2_c=-(car_km*col('e_car')+taxi_km*e_u)*365/1e6
    human=D*ku+car_km+taxi_km; way=Wt*kw
    r_inj=RATE_CITY*col('mult')*col('inv'); r_ksi=KSI_YEAR/VKT_YEAR*col('mult')*col('inv')
    inj=(human-way*col('rr_inj'))*r_inj*365; ksi=(human-way*col('rr_ksi'))*r_ksi*365
    yr=lambda a:a.reshape(a.shape[0],15,12).mean(2)
    return dict(waymoTrips=yr(Wt),fleet=yr(Wt/col('tpv')),share=yr(Wt/(Wt+UL))*100,inZone=yr(S)*100,baseline=yr(M),human=yr(UL),displaced=yr(D),
      fte=yr(D*MIN_APP/60/FTE_H_DAY),fares=yr(D*FARE*365/1e6),netKm=yr(way-human),injury=yr(inj),ksi=yr(ksi),co2=yr(co2_w+co2_u+co2_c),
      co2w=yr(co2_w),co2u=yr(co2_u),co2c=yr(co2_c))
band=lambda a:dict(p10=np.percentile(a,10,axis=0).round(3).tolist(),p50=np.percentile(a,50,axis=0).round(3).tolist(),p90=np.percentile(a,90,axis=0).round(3).tolist())
i35=list(YEARS).index(2035)
TORN=[('Ride-hail fleet goes electric (ZEV rule)','zev',1,0),('What Waymo trips replace (Uber/Lyft share)','d',.55,.85),('Waymo market share ceiling','ceil',None,None),('Grid factor: average vs marginal','gridw',0,1),('Waymo energy use','kwh_w',.32,.46),('Waymo occupied km share','occ_w',.65,.52),('Share of non-Uber trips from private cars','auto',.15,.35)]
out={}
for sc,c in SC.items():
    p=draw(sc); R=run(p)
    med={k:np.array([np.median(v)]) for k,v in p.items()}
    med['zev']=np.array([1.]) if p['zev'].mean()>=.5 else np.array([0.])
    torn=[]
    for lab,k,lo,hi in TORN:
        if lo is None: lo,hi=SC[sc]['ceil'][0],SC[sc]['ceil'][2]
        v=[]
        for val in (lo,hi):
            q=dict(med); q[k]=np.array([float(val)]); v.append(float(run(q)['co2'][0,i35]))
        torn.append(dict(label=lab,low=round(v[0]),high=round(v[1])))
    torn.sort(key=lambda r:-abs(r['high']-r['low']))
    # Map schedule from median launch and pace.
    L=float(np.median(p['launch'])); pace=c['pace']; wo={}
    for i,w in enumerate(order):
        if i+1>c['kmax']: continue
        wo[str(w)]=int(np.floor(L+max(i+1-3,0)/pace))
    # Allocate displacement by ward and collisions by neighbourhood.
    disp=np.median(R['displaced'],axis=0); inj=np.median(R['injury'],axis=0)
    wd={str(w):[0]*15 for w in order}; ha={str(x):[0]*15 for x in h.hood}
    for yi,y in enumerate(YEARS):
        op=[int(w) for w,v in wo.items() if v<=y]
        if not op or disp[yi]<=0: continue
        q=g[g.o.isin(op)&g.d.isin(op)].groupby('o').trips.sum(); q=q/q.sum()
        for w,v in q.items(): wd[str(w)][yi]=round(float(v*disp[yi]))
        m=h[h.ward.isin(op)]; wt=(m.km_day*m.rate); wt=wt/wt.sum()
        for x,v in zip(m.hood,wt): ha[str(x)][yi]=round(float(v*inj[yi]),2)
    out[sc]=dict(label=c['label'],summary=c['summary'],launch=f"{int(L)}-{int((L%1)*12)+1:02d}",wardOpen=wo,inZone=np.median(R['inZone'],axis=0).round(2).tolist(),
      series={k:band(v) for k,v in R.items() if k not in('inZone','co2w','co2u','co2c')},wardDisplaced=wd,hoodAvoided=ha,
      co2Parts=[dict(label='Waymo electricity',value=round(float(np.median(R['co2w'][:,i35])))),dict(label='Uber/Lyft km removed',value=round(float(np.median(R['co2u'][:,i35])))),dict(label='Private car and taxi km removed',value=round(float(np.median(R['co2c'][:,i35])))),dict(label='Net',value=round(float(np.median(R['co2'][:,i35]))))],
      tornado=torn)
    for y in (2030,2035,2040):
        i=list(YEARS).index(y); print(sc,y,{k:[round(float(np.percentile(R[k][:,i],q)),1) for q in (10,50,90)] for k in ['waymoTrips','fleet','share','fte','injury','ksi','netKm','co2']})
    print(sc,'zev on/off co2 2035',round(float(np.median(R['co2'][p['zev']==1,i35]))),round(float(np.median(R['co2'][p['zev']==0,i35]))),'P(co2>0)',round(float((R['co2'][:,i35]>0).mean()),2),'human trips below 2026 in',[int(y) for y,v in zip(YEARS,np.median(R['human'],axis=0)) if v<np.median(R['baseline'][:,0])][:1])

m=s.set_index('dt').reported_trips_started.resample('MS').mean().round()
q=s[s.dt>='2025-01-01'].copy(); q['m']=q.dt.dt.strftime('%Y-%m')
sup=q.groupby('m').agg(vehicles=('active_vehicles','mean'),wait=('waittime_nonwav_avg','mean')).round(1).reset_index().to_dict('records')
out_ev=dict(ramp=dict(series=ramp['series'],K=ramp['logistic']['K'],r=ramp['logistic']['r'],t50=ramp['t50'],t90=ramp['t90'],holdout=ramp['logistic']['holdout_mape6'],occ=ramp['occ_2026']),
 market=dict(months=[d.strftime('%Y-%m') for d in m.index],tripsDay=m.tolist(),backtestErr=mk['backtest_err'],naiveErr=mk['naive_err'],g0=mk['g0'],tau=mk['tau'],ttm=mk['ttm_trips_day']),
 supply=sup,weather={k:dw[k] for k in ['model_wape','naive_week_wape','baseline4wk_wape','snow_model_wape','snow_base_wape','eff','share_trips_snow24_ge1','share_trips_snow24_ge5']},
 collisions={k:cm[k] for k in ['temporal','spatial','importance','nsa_share']},
 constants=dict(minApp=MIN_APP,fare=FARE,km=KM,rrInj=RR_INJ,rhMult=RH_MULT,injYear=INJ_YEAR,ksiYear=KSI_YEAR,order=order,coverage=cov.round(4).tolist()))
json.dump(dict(years=YEARS.tolist(),scenarios=out,evidence=out_ev),open('public/data/model.json','w'),separators=(',',':'))
