"""Waymo California monthly series.
2025-01 onward: CPUC filings (primary). Earlier months: avrideshare tracker, which republishes CPUC.
"""
import re, html, zipfile, glob
import pandas as pd
rows=[]
for z in sorted(glob.glob('data/raw/cpuc/*.zip')):
    zf=zipfile.ZipFile(z)
    for n in zf.namelist():
        b=n.split('/')[-1].lower()
        if 'drivered' in n.lower(): continue
        if b.endswith('.csv') and re.search(r'month[-_ ]?(level|_part0)',b) and 'tract' not in b:
            rows.append(pd.read_csv(zf.open(n),thousands=','))
c=pd.concat(rows).drop_duplicates(['Year','Month'])
c['month']=pd.to_datetime(dict(year=c.Year,month=c.Month,day=1))
for k in ['TotalVMTPeriod1','TotalVMTPeriod2','TotalVMTPeriod3','TotalVMTZEV','TotalTrips','TotalPassengersCarried','TotalPMT','TotalWaiting']:
    c[k]=pd.to_numeric(c[k].astype(str).str.replace(',',''),errors='coerce')
c=c.rename(columns={'TotalTrips':'trips','TotalPassengersCarried':'passengers','TotalVMTZEV':'vmt','TotalVMTPeriod1':'p1','TotalVMTPeriod2':'p2','TotalVMTPeriod3':'p3','TotalPMT':'pmt','TotalWaiting':'waiting'})
c=c[['month','trips','passengers','vmt','p1','p2','p3','pmt','waiting']].assign(src='CPUC filing')

t=re.sub(r'<[^>]+>','|',open('data/raw/cpuc/avrideshare_waymo.html').read()); t=re.sub(r'\|+','|',html.unescape(t))
pat=re.compile(r'\|((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) 20\d\d)\|([\d,]+)\+?\|([\d,]+)\+?\|([\d,\.]+)\+?\|([\d\.]+)%')
r=[]
for m in pat.finditer(t):
    r.append(dict(month=pd.to_datetime(m[1],format='%b %Y'),trips=int(m[2].replace(',','')),passengers=int(m[3].replace(',','')),vmt=float(m[4].replace(',','')),share=float(m[5])))
a=pd.DataFrame(r).drop_duplicates('month')
print(a.head(3)); print(len(a))
a=a[~a.month.isin(c.month)].assign(src='CPUC via avrideshare')
s=pd.concat([c,a]).sort_values('month').reset_index(drop=True)
s['occ']=s.p3/s.vmt
s['dead_miles_per_trip']=(s.p1+s.p2)/s.trips
s['paid_mi_per_trip']=s.p3/s.trips
s['trips_day']=s.trips/s.month.dt.days_in_month
s.to_csv('data/interim/waymo_ca_monthly.csv',index=False)
print(s[['month','trips','trips_day','vmt','occ','share','paid_mi_per_trip','src']].round(3).to_string())
