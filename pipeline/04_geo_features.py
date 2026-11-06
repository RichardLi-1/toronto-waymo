"""Neighbourhood features: census 2021 + OSM road length by class + ward lookup + VKT weights."""
import numpy as np, pandas as pd, geopandas as gpd, osmnx as ox, warnings
warnings.filterwarnings('ignore')
n=gpd.read_file('data/raw/geo/neighbourhoods.geojson')[['AREA_SHORT_CODE','AREA_NAME','geometry']]
n.columns=['hood','name','geometry']; n['hood']=n.hood.astype(int)
wd=gpd.read_file('data/raw/geo/wards.geojson')[['AREA_SHORT_CODE','AREA_NAME','geometry']]; wd.columns=['ward','ward_name','geometry']
wd['ward']=wd.ward.astype(int)
u=n.to_crs(26917); n['km2']=u.area/1e6
c=u.copy(); c['geometry']=u.representative_point(); j=gpd.sjoin(c,wd.to_crs(26917),predicate='within')[['hood','ward','ward_name']]
n=n.merge(j,on='hood',how='left')

x=pd.read_excel('data/raw/geo/nbhd_2021.xlsx',header=None)
lab=x[0].astype(str).str.strip(); ids=x.iloc[1,1:].astype(float).astype(int).values
def row(pat,first=True):
    i=lab[lab.str.contains(pat,regex=True)].index[0]
    return pd.to_numeric(x.iloc[i,1:].astype(str).str.replace(',',''),errors='coerce').values
f=pd.DataFrame(dict(hood=ids,pop=row(r'^Total - Age groups of the population'),income=row(r'^Median total income of household in 2020'),
    commute_all=row(r'^Total - Main mode of commuting'),car=row(r'^Car, truck or van$'),transit=row(r'^Public transit$'),walk=row(r'^Walked$'),bike=row(r'^Bicycle$'),
    age65=row(r'^65 years and over$'),age0=row(r'^0 to 14 years$')))
for k in ['car','transit','walk','bike']: f[k+'_sh']=f[k]/f.commute_all
f['age65_sh']=f.age65/f['pop']; f['age0_sh']=f.age0/f['pop']
n=n.merge(f.drop(columns=['car','transit','walk','bike','commute_all','age65','age0']),on='hood')
n['density']=n['pop']/n.km2

G=ox.load_graphml('data/interim/toronto_drive.graphml'); e=ox.graph_to_gdfs(G,nodes=False)[['highway','length','geometry']]
e['hw']=e.highway.apply(lambda v:v[0] if isinstance(v,list) else v)
cls={'motorway':'expressway','motorway_link':'expressway','trunk':'major','trunk_link':'major','primary':'major','primary_link':'major','secondary':'minor','secondary_link':'minor','tertiary':'collector','tertiary_link':'collector'}
e['cls']=e.hw.map(cls).fillna('local')
m=e.to_crs(26917); m['geometry']=m.interpolate(.5,normalized=True) if False else m.geometry.interpolate(.5,normalized=True)
s=gpd.sjoin(m[['cls','length','geometry']],n.to_crs(26917)[['hood','geometry']],predicate='within')
r=s.pivot_table(index='hood',columns='cls',values='length',aggfunc='sum',fill_value=0)/2000   # both directions -> centreline km
r.columns=['km_'+c for c in r.columns]; n=n.merge(r.reset_index(),on='hood',how='left').fillna(0)
# Traffic weights by road class: midpoints of the City of Toronto road classification AADT ranges.
AADT=dict(km_expressway=100000,km_major=30000,km_minor=13000,km_collector=5000,km_local=1200)
n['vkt_w']=sum(n[k]*v for k,v in AADT.items() if k in n)
n.drop(columns='geometry').to_parquet('data/interim/hood_features.parquet')
n[['hood','name','ward','geometry']].to_file('data/interim/hoods.geojson',driver='GeoJSON')
print(n.drop(columns='geometry').describe().T[['mean','min','max']].round(2).to_string()); print(n.ward.isna().sum(),n['pop'].sum(),n.km2.sum())
