"""Small geometry and point files for the browser."""
import json, warnings
import pandas as pd, geopandas as gpd
warnings.filterwarnings('ignore')
w=gpd.read_file('data/raw/geo/wards.geojson')[['AREA_SHORT_CODE','AREA_NAME','geometry']]; w.columns=['ward','name','geometry']; w['ward']=w.ward.astype(int)
rp=w.to_crs(26917).representative_point().to_crs(4326); w['lon']=rp.x.round(4); w['lat']=rp.y.round(4)
w['geometry']=w.geometry.simplify(.0004); w.to_file('public/data/wards.geojson',driver='GeoJSON',COORDINATE_PRECISION=5)
h=gpd.read_file('data/interim/hoods.geojson'); h['geometry']=h.geometry.simplify(.0003); h.to_file('public/data/hoods.geojson',driver='GeoJSON',COORDINATE_PRECISION=5)
c=pd.read_csv('data/raw/collisions/traffic_collisions.csv',low_memory=False,usecols=['OCC_YEAR','INJURY_COLLISIONS','FATALITIES','LONG_WGS84','LAT_WGS84','PEDESTRIAN','BICYCLE'])
c=c[c.OCC_YEAR.between(2023,2025)&(c.INJURY_COLLISIONS.eq('YES')|(c.FATALITIES.fillna(0)>0))&c.LONG_WGS84.between(-79.7,-79.1)&c.LAT_WGS84.between(43.55,43.9)]
v=(c.PEDESTRIAN.eq('YES')|c.BICYCLE.eq('YES')).astype(int)
json.dump([[round(a,4),round(b,4),int(k)] for a,b,k in zip(c.LONG_WGS84,c.LAT_WGS84,v)],open('public/data/collisions.json','w'),separators=(',',':'))
print(len(c),v.mean())
