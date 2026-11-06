"""Turn real ward-to-ward demand into street-level trips for the map.

The City publishes trips by ward and hour, not addresses. So each sampled trip's
ward pair, hour and duration are real, while its exact start and end are synthetic:
street nodes drawn inside the ward, weighted by population density.

Writes public/data/trips.json and data/interim/hood_km.parquet (ride-hail km by neighbourhood)."""
import json, re, sys, warnings
import numpy as np, pandas as pd, geopandas as gpd, osmnx as ox, scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import LineString
warnings.filterwarnings('ignore')
rng=np.random.default_rng(11)
SAMPLE=7          # one line on the map = 7 real trips
DOW=4             # a typical Friday
ANCHORS=dict(core=90,other=45)

G=ox.load_graphml('data/interim/toronto_drive.graphml')
nodes,edges=ox.graph_to_gdfs(G)
nid=nodes.index.values; pos={n:i for i,n in enumerate(nid)}
SPEED=dict(motorway=85,motorway_link=50,trunk=60,trunk_link=40,primary=45,primary_link=35,secondary=40,secondary_link=30,tertiary=35,tertiary_link=30,residential=25,unclassified=25,living_street=15,service=15)
hw=edges.highway.apply(lambda v:v[0] if isinstance(v,list) else v)
tt=edges['length'].values/(hw.map(SPEED).fillna(25).values/3.6)
idx=edges.index.to_frame(index=False)
u=idx.iloc[:,0].map(pos).values; v=idx.iloc[:,1].map(pos).values
ordr=np.lexsort((tt,v,u)); uu,vv,ww=u[ordr],v[ordr],tt[ordr]
keep=np.r_[True,(uu[1:]!=uu[:-1])|(vv[1:]!=vv[:-1])]
N=len(nid); A=sp.csr_matrix((ww[keep],(uu[keep],vv[keep])),shape=(N,N))
L=sp.csr_matrix((edges['length'].values[ordr][keep],(uu[keep],vv[keep])),shape=(N,N))
lon=nodes.x.values; lat=nodes.y.values

# Geometry of the edges (for curved roads).
geo={}
for (a,b),g in zip(zip(uu[keep],vv[keep]),edges.geometry.values[ordr][keep]): geo[(a,b)]=g

hoods=gpd.read_file('data/interim/hoods.geojson'); hf=pd.read_parquet('data/interim/hood_features.parquet')[['hood','density']]
hoods=hoods.merge(hf,on='hood')
pts=gpd.GeoDataFrame({'i':np.arange(N)},geometry=gpd.points_from_xy(lon,lat),crs=4326)
j=gpd.sjoin(pts,hoods[['hood','ward','density','geometry']],predicate='within').drop_duplicates('i')
bad=set(np.r_[u[hw.isin(['motorway','motorway_link','trunk_link']).values],v[hw.isin(['motorway','motorway_link','trunk_link']).values]])
hood_of=np.full(N,-1); hood_of[j.i.values]=j.hood.values   # every node, for exposure
j=j[~j.i.isin(bad)]                                          # trips don't start on expressways

od=pd.read_parquet('data/interim/od_recent.parquet')
print('total',od.trips.sum())
ward_lbl=lambda s:(int(s[:2]) if re.match(r'^\d\d - ',s) else s)
od['o2']=od.o.map(ward_lbl); od['d2']=od.d.map(ward_lbl)
# Records rolled up for privacy ("Not included elsewhere") are spread over wards by marginal share.
wards=list(range(1,26)); tot=od[od.o2.isin(wards)].groupby('o2').trips.sum(); wshare=(tot/tot.sum())
def spread(df,col):
    m=df[col]=='Not included elsewhere'; a=df[~m]; b=df[m]
    parts=[a]
    for w,s in wshare.items():
        c=b.copy(); c[col]=w
        for k in ['trips','fare','wait','dist','dur']: c[k]=c[k]*s
        parts.append(c)
    return pd.concat(parts)
od=spread(spread(od,'o2'),'d2')
OUT=[k for k in od.o2.unique() if isinstance(k,str)]
g=od.groupby(['o2','d2','dow','hour'],as_index=False)[['trips','fare','wait','dist','dur']].sum()
g.astype({'o2':str,'d2':str}).to_parquet('data/interim/od_clean.parquet')
in_t=lambda s:s.apply(lambda x:isinstance(x,(int,np.integer)))
both_out=(~in_t(g.o2))&(~in_t(g.d2))
print('share outside-only',g[both_out].trips.sum()/g.trips.sum())
fr=g[(g.dow==DOW)&~both_out].copy()
NF=len(pd.date_range('2025-07-01','2026-07-31',freq='W-FRI'))
fr['per_day']=fr.trips/NF; print('typical friday trips',fr.per_day.sum())
fr['km']=fr.dist/fr.trips; fr['mins']=fr.dur/fr.trips

# Gateways for trips leaving the city: nearest street node to each municipality's main approach.
GATE={'Mississauga':(-79.62,43.62),'Pearson Airport':(-79.6130,43.6815),'Vaughan':(-79.50,43.795),'Markham':(-79.33,43.812),'Richmond Hill':(-79.42,43.805),'Brampton':(-79.66,43.73),'Pickering':(-79.12,43.815),'Ajax':(-79.115,43.80),'Whitby':(-79.11,43.79),'Oshawa':(-79.108,43.785),'Oakville':(-79.69,43.59),'Burlington':(-79.695,43.585),'Other Municipality':(-79.40,43.855),'Not included elsewhere':(-79.40,43.855)}
gate={k:int(np.argmin((lon-a)**2+(lat-b)**2)) for k,(a,b) in GATE.items()}
anch={}
for w in wards:
    c=j[j.ward==w]; p=c.density.values**.8; p=p/p.sum()
    n=ANCHORS['core'] if w in (10,11,13) else ANCHORS['other']
    anch[w]=rng.choice(c.i.values,size=n,replace=True,p=p)
pick=lambda k:anch[k][rng.integers(len(anch[k]))] if k in anch else gate[k]
trips=[]
for r in fr.itertuples():
    n=rng.poisson(r.per_day/SAMPLE)
    for _ in range(n):
        a,b=pick(r.o2),pick(r.d2)
        if a==b: continue
        trips.append((a,b,r.o2,r.d2,r.hour,r.km,r.mins))
print('sampled',len(trips))
src=sorted({t[0] for t in trips}); pred={}
need={}
for t in trips: need.setdefault(t[0],set()).add(t[1])
paths={}
CH=120
for s in range(0,len(src),CH):
    ch=src[s:s+CH]; _,P=dijkstra(A,indices=ch,return_predecessors=True)
    for i,a in enumerate(ch):
        for b in need[a]:
            q=[b];x=b
            while x!=a and x>=0:
                x=P[i,x]
                if x<0: break
                q.append(x)
            if x==a: paths[(a,b)]=q[::-1]
    print(s,len(paths),flush=True)
keys=list(paths); kidx={k:i for i,k in enumerate(keys)}
hkm={}; routes=[]; rkm=[]
for k in keys:
    p=paths[k]; c=[]; km=0
    for a,b in zip(p[:-1],p[1:]):
        gm=geo.get((a,b)); seg=np.array(gm.coords) if gm is not None else np.array([[lon[a],lat[a]],[lon[b],lat[b]]])
        c.extend(seg[:-1].tolist()); l=L[a,b]/1000; km+=l
    c.append([lon[p[-1]],lat[p[-1]]])
    ls=LineString(c).simplify(.00012,preserve_topology=False)
    q=np.round(np.array(ls.coords)*1e5).astype(np.int64)
    d=np.r_[q[:1],np.diff(q,axis=0)]
    routes.append(d.ravel().tolist()); rkm.append(km)
cnt={}
T=[]
for a,b,o,d,h,km,mins in trips:
    k=(a,b)
    if k not in kidx: continue
    cnt[k]=cnt.get(k,0)+1
    start=h*60+rng.uniform(0,60)
    dur=max(3.0,mins*rng.lognormal(0,.25))
    ow=o if isinstance(o,(int,np.integer)) else 0
    dw=d if isinstance(d,(int,np.integer)) else 0
    T.append([kidx[k],round(start,1),round(dur,1),int(ow),int(dw),round(float(rng.uniform()),3),int(rng.integers(0,1000))])
# Ride-hail on-trip km by neighbourhood (scaled to a real Friday), for collision exposure.
for k,c in cnt.items():
    p=paths[k]
    for a,b in zip(p[:-1],p[1:]):
        h=hood_of[a] if hood_of[a]>=0 else hood_of[b]
        if h>=0: hkm[h]=hkm.get(h,0)+c*L[a,b]/1000*SAMPLE
pd.DataFrame({'hood':list(hkm),'km_day':list(hkm.values())}).to_parquet('data/interim/hood_km.parquet')
T.sort(key=lambda t:t[1])
act=np.zeros(1500)
for t in T:
    a=int(t[1]); b=min(1499,int(t[1]+t[2])); act[a:b+1]+=1
json.dump(dict(sample=SAMPLE,day='Typical Friday, Jul 2025 to Jul 2026',routes=routes,trips=T,active=act[:1440].round().astype(int).tolist()),open('public/data/trips.json','w'),separators=(',',':'))
print('trips',len(T),'routes',len(routes),'mean routed km',np.mean(rkm),'pts',sum(len(r) for r in routes)//2, 'peak',act.max())
print('hood km',sum(hkm.values()))
