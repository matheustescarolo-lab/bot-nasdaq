import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
D=pd.read_pickle('flujo.pkl')            # P&L diario por estrategia (1 MNQ c/u, costos incluidos)
idx={pd.Timestamp(g.d):k for k,g in enumerate(arr)}
P=[]
for k in range(20,len(arr)):
    g=arr[k]; pc=arr[k-1].c[-1]
    P.append(dict(fecha=pd.Timestamp(g.d), a1500=g.c[65]/pc-1, a1530=g.c[71]/pc-1, ult30=g.c[77]/g.c[71]-1, ult60=g.c[77]/g.c[65]-1, a1545=g.c[74]/pc-1, ult15=g.c[77]/g.c[74]-1))
P=pd.DataFrame(P).set_index('fecha'); X=D.join(P)
t=lambda z: z.mean()/z.std()*np.sqrt(len(z))
print('=== 1) ETF apalancados: ¿el movimiento del día sigue en los últimos minutos?')
for antes,despues in (('a1500','ult60'),('a1530','ult30'),('a1545','ult15')):
    for u in (0.01,0.02):
        s=np.sign(X[antes]).where(X[antes].abs()>u,0); r=(s*X[despues]).replace(0,np.nan).dropna()
        usd=r*X.loc[r.index].index.map(lambda d: arr[idx[d]].c[-1]).values*USD - COSTO
        m=len(usd)//2; print(f'  {antes}>{u:.0%} → seguir {despues}: {len(usd)} días · ${usd.mean():6.1f}/trade · t {t(usd):5.2f} · mitades ${usd.iloc[:m].mean():.1f}/${usd.iloc[m:].mean():.1f}')
# 2) OPEX
def tercer_viernes(y,mo):
    d=pd.Timestamp(y,mo,15); return d+pd.Timedelta(days=(4-d.weekday())%7)
op=[tercer_viernes(y,mo) for y in range(2019,2027) for mo in range(1,13)]
X['opex']=X.index.isin(op); X['triple']=X.opex & X.index.month.isin([3,6,9,12])
X['sem_opex']=X.index.to_period('W').isin(pd.DatetimeIndex(op).to_period('W'))
X['lun_post']=X.index.isin([d+pd.Timedelta(days=3) for d in op])
print('\n=== 2) Vencimiento de opciones (ORB / Ruido / total, $/día, 1 MNQ c/u)')
base=X[~X.sem_opex]
print(f'  días normales: {len(base)} · ORB {base.orb.mean():.1f} · Ruido {base.ru.mean():.1f} · total {base.tot.mean():.1f}')
for c in ('opex','triple','sem_opex','lun_post'):
    a=X[X[c]]; print(f'  {c:<9}: {len(a):4} días · ORB {a.orb.mean():6.1f} · Ruido {a.ru.mean():6.1f} · total {a.tot.mean():6.1f} · t vs resto {(a.tot.mean()-X[~X[c]].tot.mean())/np.sqrt(a.tot.var()/len(a)+X[~X[c]].tot.var()/(len(X)-len(a))):5.2f}')
# 3) Fin de mes
X['mes']=X.index.to_period('M'); X['n']=X.groupby('mes').cumcount(); X['N']=X.groupby('mes').tot.transform('size'); X['desde_fin']=X.N-X.n
print('\n=== 3) Fin / inicio de mes ($/día total)')
for nom,msk in (('últimos 2 días',X.desde_fin<=2),('primeros 2',X.n<2),('fin de trimestre (últ. 2)',(X.desde_fin<=2)&X.index.month.isin([3,6,9,12])),('resto',(X.desde_fin>2)&(X.n>=2))):
    a=X[msk]; print(f'  {nom:<26}{len(a):4} días · ORB {a.orb.mean():6.1f} · Ruido {a.ru.mean():6.1f} · total {a.tot.mean():6.1f}')
# rebalanceo: mes muy alcista -> presión vendedora últimos días
cm=X.groupby('mes').ret.apply(lambda r:(1+r).prod()-1); X['mtd_prev']=X.groupby('mes').ret.transform(lambda r:(1+r).cumprod().shift(1).fillna(1)-1)
fin=X[X.desde_fin<=2]; q=pd.qcut(fin.mtd_prev,3,labels=['mes bajista','neutro','mes alcista'])
print('  Nasdaq en los últimos 2 días (pb) según el mes:', fin.groupby(q,observed=True).ret.mean().mul(1e4).round(1).to_dict(), '| largos−cortos bot:', fin.groupby(q,observed=True).apply(lambda a:((a.oL+a.rL)-(a.oS+a.rS)).mean()).round(1).to_dict())
X.to_pickle('obligados.pkl')
