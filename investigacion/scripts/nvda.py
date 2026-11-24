import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
REP="""2019-02-14 2019-05-16 2019-08-15 2019-11-14 2020-02-13 2020-05-21 2020-08-19 2020-11-18 2021-02-24 2021-05-26 2021-08-18 2021-11-17 2022-02-16 2022-05-25 2022-08-24 2022-11-16
2023-02-22 2023-05-24 2023-08-23 2023-11-21 2024-02-21 2024-05-22 2024-08-28 2024-11-20 2025-02-26 2025-05-28 2025-08-27 2025-11-19 2026-02-25 2026-05-20 2026-08-26""".split()
C=np.load('caminos_C.npy'); W=np.load('caminos_W.npy')
fechas=[pd.Timestamp(arr[k].d) for k in range(20,len(arr))]; pos={f:i for i,f in enumerate(fechas)}
despues=[]
for r in pd.to_datetime(REP):
    sig=[f for f in fechas if f>r]
    if sig: despues.append(pos[sig[0]])
def dia(i, n=6, meta=1550):
    c=n*C[i]; w=n*W[i]; peor=0.0
    for t in range(78):
        peor=min(peor,w[t])
        if c[t]>=meta: return c[t], peor
    return c[-1], peor
T=pd.read_pickle('trades8.pkl'); T['f']=T.fecha.dt.normalize()
dset=set(fechas[i] for i in despues)
print(f'Día después del reporte de Nvidia: {len(despues)} casos (2019–2026)')
for e in ('orb','ruido'):
    D=T[T.estr==e]; g=D[D.f.isin(dset)]; o=D[~D.f.isin(dset)]
    t=(g.pnl.mean()-o.pnl.mean())/(g.pnl.std()/np.sqrt(len(g)))
    print(f'  {e:<6} {len(g)} trades · aciertos {g.gana.mean():.0%} (normal {o.gana.mean():.0%}) · US$/trade {g.pnl.mean():.1f} (normal {o.pnl.mean():.1f}) · t {t:.2f}')
print('\nModo examen (6 MNQ, meta 1,550), día después de Nvidia:')
for i in despues:
    k=i+20; g=arr[k]; gap=g.o[0]/arr[k-1].c[-1]-1; mov=g.c[-1]/g.o[0]-1; r,p=dia(i)
    print(f'  {fechas[i].date()} · gap {gap:+.1%} · apertura→cierre {mov:+.1%} · bot {r:+,.0f} (peor {p:,.0f})')
x=np.array([dia(i)[0] for i in despues]); todos=np.array([dia(i)[0] for i in range(len(C))])
print(f'\nPromedio ${x.mean():+,.0f} (normal ${todos.mean():+,.0f}) · gana {np.mean(x>0):.0%} (normal {np.mean(todos>0):.0%}) · llega a la meta {np.mean(x>=1550):.0%} (normal {np.mean(todos>=1550):.0%}) · pierde >1,000 {np.mean(x<=-1000):.0%} (normal {np.mean(todos<=-1000):.0%})')
gaps=np.array([arr[i+20].o[0]/arr[i+19].c[-1]-1 for i in despues]); movs=np.array([arr[i+20].c[-1]/arr[i+20].o[0]-1 for i in despues])
print(f'Días con gap alcista > +0.5%: {np.sum(gaps>0.005)} · de esos, el Nasdaq siguió subiendo desde la apertura en {np.mean(movs[gaps>0.005]>0):.0%} · movimiento medio apertura→cierre {movs[gaps>0.005].mean():+.2%}')
