"""(a) Fit saturating ramp curves to Waymo's California series, with leave-future-out validation.
   (b) Fit the decay of Toronto ride-hail growth and backtest it.
Writes data/interim/ramp_fit.json and market_fit.json."""
import json, warnings
import numpy as np, pandas as pd
from scipy.optimize import least_squares
warnings.filterwarnings('ignore')
rng=np.random.default_rng(7)

w=pd.read_csv('data/interim/waymo_ca_monthly.csv',parse_dates=['month'])
w['t']=(w.month.dt.year-2023)*12+w.month.dt.month-8   # months since commercial launch, Aug 2023
t=w.t.values.astype(float); y=w.trips_day.values

def logistic(p,t): K,r,t0=p; return K/(1+np.exp(-r*(t-t0)))
def gompertz(p,t): K,r,t0=p; return K*np.exp(-np.exp(-r*(t-t0)))
def fit(f,t,y,p0):
    # Robust loss on log scale. The June-July 2025 filings fall about 30% below trend.
    res=least_squares(lambda p:np.log(f(p,t)+1)-np.log(y+1),p0,loss='soft_l1',f_scale=.1,
                      bounds=([1e4,.02,0],[5e5,1,120]))
    return res.x
out={}
for name,f,p0 in [('logistic',logistic,[5e4,.2,24]),('gompertz',gompertz,[6e4,.12,22])]:
    p=fit(f,t,y,p0); r=np.log(f(p,t))-np.log(y)
    # Leave-future-out: fit to month k, score the following 6 months.
    errs=[]
    for k in range(20,len(t)-6):
        q=fit(f,t[:k],y[:k],p); e=np.abs(f(q,t[k:k+6])-y[k:k+6])/y[k:k+6]; errs.append(np.median(e))
    # Residual bootstrap for parameter uncertainty.
    bs=[]
    for _ in range(400):
        yb=f(p,t)*np.exp(rng.choice(r,len(r)))
        bs.append(fit(f,t,yb,p))
    bs=np.array(bs)
    out[name]=dict(K=p[0],r=p[1],t0=p[2],rmse_log=float(np.sqrt(np.median(r**2))),holdout_mape6=float(np.median(errs)),
                   K_p10=float(np.percentile(bs[:,0],10)),K_p90=float(np.percentile(bs[:,0],90)),
                   r_p10=float(np.percentile(bs[:,1],10)),r_p90=float(np.percentile(bs[:,1],90)))
    print(name,{k:round(float(v),3) for k,v in out[name].items()})
# Months from commercial start to 50% and 90% of the plateau.
best=min(out,key=lambda k:out[k]['holdout_mape6']); b=out[best]
f={'logistic':logistic,'gompertz':gompertz}[best]
tt=np.arange(0,160,.25); c=f((b['K'],b['r'],b['t0']),tt)/b['K']
out['best']=best; out['t50']=float(tt[np.argmax(c>=.5)]); out['t90']=float(tt[np.argmax(c>=.9)])
print('best',best,'t50',out['t50'],'t90',out['t90'])
out['series']=[dict(m=m.strftime('%Y-%m'),trips_day=round(float(v)),fit=round(float(f((b['K'],b['r'],b['t0']),np.array([q]))[0]))) for m,v,q in zip(w.month,y,t)]
late=w[w.month>='2026-01-01']
out['occ_2026']=float((late.p3.sum())/late.vmt.sum()); out['paid_mi_trip_2026']=float(late.p3.sum()/late.trips.sum())
out['total_mi_trip_2026']=float(late.vmt.sum()/late.trips.sum()); print({k:round(out[k],3) for k in ['occ_2026','paid_mi_trip_2026','total_mi_trip_2026']})
json.dump(out,open('data/interim/ramp_fit.json','w'),indent=1)

# ---- Toronto market
s=pd.read_csv('data/raw/ptc/summary_stats.csv',parse_dates=['dt']).set_index('dt')
m=s.reported_trips_started.resample('MS').sum()/s.reported_trips_started.resample('MS').count()
yoy=np.log(m/m.shift(12)).dropna()
g=yoy['2023-07':]
x=(g.index.year+(g.index.month-1)/12).values.astype(float)
def gfun(p,x): g0,tau=p; return .012+(g0-.012)*np.exp(-(x-2023.5)/tau)
pf=least_squares(lambda p:gfun(p,x)-g.values,[.3,3],bounds=([.01,.3],[1,30])).x
print('growth fit g0,tau',pf,'latest yoy',g.tail(3).round(3).values)
# Backtest: fit growth decay through Jul 2025, project level to Jul 2026.
cut='2025-07'; gi=g[:cut]; xi=x[:len(gi)]
pb=least_squares(lambda p:gfun(p,xi)-gi.values,[.3,3],bounds=([.01,.3],[1,30])).x
base=m['2024-08':cut].mean(); xx=np.arange(2025+7/12,2026+7/12,1/12)
proj=base*np.exp(np.mean([gfun(pb,np.array([q]))[0] for q in xx]))
act=m['2025-08':'2026-07'].mean(); naive=base
print('backtest proj',round(proj),'actual',round(act),'err%',round((proj/act-1)*100,1),'naive err%',round((naive/act-1)*100,1))
res=(g.values-gfun(pf,x)).std()
ann=m['2025-08':'2026-07'].mean()
json.dump(dict(g0=float(pf[0]),tau=float(pf[1]),resid_sd=float(res),ttm_trips_day=float(ann),backtest_err=float(proj/act-1),naive_err=float(naive/act-1)),open('data/interim/market_fit.json','w'),indent=1)
print('ttm trips/day',round(ann))
