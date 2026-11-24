import os, numpy as np, pandas as pd
exec(open('orb_real.py').read().split("Z=dict(")[0])      # arr, orb_v, gestiona, USD, CIERRE, FOMC
def rth(path):
    x=pd.read_csv(path,parse_dates=['ny']).set_index('ny'); x=x[(x.index.time>=pd.Timestamp('09:30').time())&(x.index.time<pd.Timestamp('16:00').time())]
    g={d:v for d,v in x.groupby(x.index.date) if len(v)==78}; return g
NQ=rth('/home/claude/bot-nasdaq/historia_nas_dukascopy.csv'); SP=rth('/home/claude/bot-nasdaq/extra/m5_usa500idxusd.csv')
H1=pd.concat([pd.read_csv(f'/home/claude/bot-nasdaq/extra/nas_h1_{y}.csv') for y in range(2019,2027)])
H1.index=pd.DatetimeIndex(pd.to_datetime(H1.timestamp,unit='ms',utc=True)).tz_convert('America/New_York').tz_localize(None); H1=H1.sort_index(); H1=H1[~H1.index.duplicated()]
# RSI continuo en 5 min
todo=pd.concat([NQ[d] for d in sorted(NQ)]); dlt=todo.close.diff(); up=dlt.clip(lower=0).ewm(alpha=1/14,adjust=False).mean(); dn=(-dlt.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean(); RSI=100-100/(1+up/dn)
dias=sorted(NQ); idx={d:i for i,d in enumerate(dias)}
filas=[]
for k in range(20,len(arr)):
    g=arr[k]; d=pd.Timestamp(g.d).date()
    if pd.Timestamp(g.d) in FOMC or d not in idx or idx[d]<21: continue
    tr=orb_v(g,True,True)
    if not tr: continue
    s,e,x,a,b=tr[0]; pnl=s*(x-e)*USD-3
    D=NQ[d]; i=idx[d]; P=[NQ[dias[j]] for j in range(i-20,i)]; ay=P[-1]
    hi,lo=g.h[:6].max(),g.l[:6].min(); R=hi-lo
    atr=np.mean([p.high.max()-p.low.min() for p in P[-14:]])
    vw=(D.close*D.tick_volume).cumsum()/D.tick_volume.cumsum()
    nivel=hi if s==1 else lo
    # noche: de 16:00 de ayer a 9:30 de hoy
    n=H1[(H1.index>=pd.Timestamp(dias[i-1])+pd.Timedelta(hours=16))&(H1.index<pd.Timestamp(d)+pd.Timedelta(hours=9,minutes=30))]
    nh,nl=(n.high.max(),n.low.min()) if len(n) else (np.nan,np.nan)
    S=SP.get(d); spc=np.nan
    if S is not None:
        sh,sl=S.high.iloc[:6].max(),S.low.iloc[:6].min(); m=S.iloc[6:a]
        up_,dn_=(m.high>sh).any(),(m.low<sl).any(); spc= s*(1 if up_ and not dn_ else -1 if dn_ and not up_ else 0)
    # desvanecer (fade): entra al revés en el nivel; stop un rango más allá; objetivo el otro lado; si no, al cierre
    fe=nivel; fst=nivel+s*R; ftg=lo if s==1 else hi; fx=None
    for j in range(a,CIERRE+1):
        if (s==1 and g.h[j]>=fst) or (s==-1 and g.l[j]<=fst): fx=fst; break
        if j>a and ((s==1 and g.l[j]<=ftg) or (s==-1 and g.h[j]>=ftg)): fx=ftg; break
    if fx is None: fx=g.c[CIERRE]
    fade=-s*(fx-fe)*USD-3
    filas.append(dict(fecha=d,lado=s,pnl=pnl,fade=fade,
        rango_atr=R/atr, rsi=s*(RSI.loc[D.index[a-1]]-50) if a>0 else np.nan,
        vol_apertura=D.tick_volume.iloc[:6].sum()/np.mean([p.tick_volume.iloc[:6].sum() for p in P]),
        vol_previa=D.tick_volume.iloc[a-1]/D.tick_volume.iloc[:a].mean(),
        vwap=s*(nivel-vw.iloc[a-1])/R, liq_ayer=((ay.high.max()-hi) if s==1 else (lo-ay.low.min()))/R,
        liq_noche=((nh-hi) if s==1 else (lo-nl))/R, gap=s*(D.open.iloc[0]-ay.close.iloc[-1])/atr,
        cierre_rango=((g.c[5]-lo) if s==1 else (hi-g.c[5]))/R, minuto=a, sp_confirma=spc,
        ret_ayer=s*(ay.close.iloc[-1]/P[-2].close.iloc[-1]-1), pos_ayer=((ay.close.iloc[-1]-ay.low.min()) if s==1 else (ay.high.max()-ay.close.iloc[-1]))/(ay.high.max()-ay.low.min())))
F=pd.DataFrame(filas); F.to_pickle('rebote.pkl')
print('trades',len(F),'· ORB $',round(F.pnl.mean(),1),'· desvanecer siempre $',round(F.fade.mean(),1),'· ORB pierde',f"{np.mean(F.pnl<0):.0%}")
