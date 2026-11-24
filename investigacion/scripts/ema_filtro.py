import os, re, numpy as np, pandas as pd
exec(open('orb_real.py').read().split("Z=dict(")[0])
h=pd.read_csv('/home/claude/bot-nasdaq/historia_nas_dukascopy.csv',parse_dates=['ny']).set_index('ny')
h=h[(h.index.time>=pd.Timestamp('09:30').time())&(h.index.time<pd.Timestamp('16:00').time())]
res={tf:{'a favor':[], 'en contra':[], 'mixto':[]} for tf in (5,15,30)}
emas={}
for tf in (5,15,30):
    b=h.resample(f'{tf}min').agg({'close':'last'}).dropna(); c=b.close
    emas[tf]=pd.DataFrame({k:c.ewm(span=k,adjust=False).mean() for k in (4,8,16)})
for k in range(20,len(arr)):
    g=arr[k]
    if pd.Timestamp(g.d) in FOMC: continue
    tr=orb_v(g,True,True)
    if not tr: continue
    s,e,x,a,b_=tr[0]; pnl=s*(x-e)*USD-3
    t_ent=pd.Timestamp(g.d)+pd.Timedelta(minutes=570+5*a)        # hora de la vela de entrada
    for tf in (5,15,30):
        E=emas[tf]; prev=E[E.index+pd.Timedelta(minutes=tf)<=t_ent]   # solo velas ya cerradas antes de entrar
        if len(prev)==0: continue
        r=prev.iloc[-1]; al= 1 if (r[4]>r[8] and r[4]>r[16]) else -1 if (r[4]<r[8] and r[4]<r[16]) else 0
        res[tf]['a favor' if al==s else 'en contra' if al==-s else 'mixto'].append(pnl)
for tf in (5,15,30):
    out=[]
    for kk,v in res[tf].items():
        v=np.array(v); out.append(f"{kk}: {len(v)} trades ${v.mean():6.1f} (t {v.mean()/v.std()*np.sqrt(len(v)):4.1f})")
    print(f"ORB con EMAs de {tf} min →", ' · '.join(out))
