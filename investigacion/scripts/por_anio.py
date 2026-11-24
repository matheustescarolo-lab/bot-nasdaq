exec(open("debrief_lib.py").read())
import pandas as pd
Co,Wo,Cr,Wr,mo,mr=escenario('ambos_sac','todo',False); mo=np.minimum(mo,2.0); mr=np.minimum(mr,2.0)
orb=mo*Co[:,-1]; ru=mr*Cr[:,-1]; tot=orb+ru
F=pd.Series(fechas[:len(tot)]) if len(fechas)>=len(tot) else None
yrs=pd.DatetimeIndex(fechas[:len(tot)]).year
# precio y volatilidad por año (para comparar en %)
x=pd.read_csv('/home/claude/bot-nasdaq/historia_nas_dukascopy.csv',parse_dates=['ny']).set_index('ny')
x=x[(x.index.time>=pd.Timestamp('09:30').time())&(x.index.time<pd.Timestamp('16:00').time())]
d=x.groupby(x.index.date).agg(h=('high','max'),l=('low','min'),c=('close','last')); d.index=pd.to_datetime(d.index)
d['rng']=(d.h-d.l)/d.c
E=(Co,Wo,Cr,Wr,mo,mr)
starts=list(range(0,len(fechas)-260,3)); sy=pd.DatetimeIndex([fechas[s] for s in starts]).year
R=np.array([plan2(s,E,4,6) for s in starts]); g=R[:,0]-(R[:,1]-R[:,2])*439*1.1
print("año | $/día 1 MNQ (ORB+ruido) | ORB | ruido | días que gana | Sharpe | precio medio | % de 1 MNQ nocional por año | rango diario medio | reto 4: no cobra, mediana 12m")
for y in sorted(set(yrs)):
    m=yrs==y; t=tot[m]; px=d.c[d.index.year==y].mean(); rg=d.rng[d.index.year==y].mean()
    mm=sy==y
    extra=f" | {np.mean(R[mm,2]==0):.0%}, ${np.median(g[mm]):,.0f}" if mm.any() else ''
    print(f"{y} | ${t.mean():6.1f} | ${orb[m].mean():5.1f} | ${ru[m].mean():5.1f} | {np.mean(t>0):.0%} | {t.mean()/t.std()*np.sqrt(252):.2f} | {px:,.0f} | {t.mean()*252/(2*px):.0%} | {rg:.2%}{extra}")
