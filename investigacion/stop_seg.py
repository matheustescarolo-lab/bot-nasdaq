import os, re, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
G={}; exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0],G)
arr=G['arr']; ruido_t=G['ruido_t']; CIERRE=G['CIERRE']
Z=np.load('final_caminos.npz',allow_pickle=True); fechas=pd.DatetimeIndex(Z['fechas']); ret1=Z['ret1']; pay=Z['pay']
W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]'); W=W.reindex(fechas)
vol=W.vol.values; r9=W.r9.values; cot=W.cot.fillna(1).values; gig=W.gig.fillna(False).values; nfp=W.nfp.fillna(False).values
ev=cot*np.where(gig,1.5,1)
mo=vol*r9*ev*np.where(ret1<-0.02,0,1)
mr=vol*r9*ev*np.where(nfp,1.5,1)*np.where(ret1<-0.01,0,1)*np.where(pay>0.8,1.5,np.where(pay<0.2,0.5,1))
idx={pd.Timestamp(d):i for i,d in enumerate(fechas)}
BASE=6; P=27000; R=[]; O=[]
for k in range(14,len(arr)):
    g=arr[k]; i=idx.get(pd.Timestamp(g.d))
    if i is None or np.isnan(mr[i]): continue
    nr=min(round(BASE*mr[i]),2*BASE); no=min(round(BASE*mo[i]),2*BASE)
    hi,lo=g.h[:6].max(),g.l[:6].min(); O.append((no,(hi-lo)/((hi+lo)/2)))
    if nr==0: continue
    hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    for s,e,x,a,b in ruido_t(g,hist,arr[k-1].c[-1]):
        adv=[(e-g.l[t])/e if s==1 else (g.h[t]-e)/e for t in range(a+1,b+1)]
        mae=max([0]+adv); res=s*(x-e)/e
        # peor caso si el bot se cae justo al entrar: la posición corre hasta el cierre (o el stop del servidor)
        rest=[(e-g.l[t])/e if s==1 else (g.h[t]-e)/e for t in range(a+1,78)]
        R.append((nr,mae,res,max([0]+rest)))
R=np.array(R); O=np.array(O)
n,mae,res,dead=R.T
print(f'operaciones de zona de ruido: {len(R)} · tamaño medio {n.mean():.1f} MNQ (base {BASE})')
print('\n¿Cuántas veces un stop en el servidor a X% habría saltado con el bot funcionando (antes de su salida normal)?')
print(' X%   veces  %ops   costo total vs. salida normal (US$, 8 años, precio 27,000)   $/día')
dias=len(set(range(len(O))))
for X in (0.005,0.0075,0.01,0.0125,0.015,0.02,0.025):
    hit=mae>=X
    # si salta: sale en -X (más 2 pts de deslizamiento) en vez del resultado normal
    costo=((-X-2/P)-res)[hit]*P*2*n[hit]
    print(f'{X*100:4.2f}  {hit.sum():5d}  {hit.mean()*100:5.2f}%  {costo.sum():>12,.0f}   {costo.sum()/dias:6.2f}')
print('\nPEOR CASO si el bot se cae justo al entrar (la posición queda sola hasta las 16:00):')
for X in (None,0.025,0.01,0.0075):
    l=np.minimum(dead, X if X else 9)*P*2*n
    print(f' stop {"ninguno" if X is None else f"{X*100:.2f}%"}: pérdida máx ${l.max():,.0f} · ops > $4,000: {(l>4000).sum()} · > $5,000: {(l>5000).sum()}')
lo_=O[:,0]*O[:,1]*P*2
print(f'\nORB (stop al otro lado del rango, ya en el servidor): pérdida si toca el stop, precio 27,000: mediana ${np.median(lo_[O[:,0]>0]):,.0f} · p95 ${np.percentile(lo_[O[:,0]>0],95):,.0f} · máx ${lo_.max():,.0f} · días > $4,000: {(lo_>4000).sum()} de {(O[:,0]>0).sum()}')
print('\nSTOP EN DÓLARES (se ajusta al tamaño): distancia = min(1.25%, presupuesto / (2 × MNQ × precio))')
for B in (2000,2500,3000,3500):
    X=np.minimum(0.0125, B/(2*n*P)); hit=mae>=X
    ef=((-X-2/P)-res)[hit]*P*2*n[hit]
    l=np.minimum(dead,X)*P*2*n+2*2*n
    print(f' ${B:,}: salta {hit.sum()} veces ({hit.mean()*100:.1f}%) · efecto {ef.sum():+,.0f} US$ en 8 años ({ef.sum()/dias:+.2f}/día) · pérdida máx si el bot muere ${l.max():,.0f}')
tot=(res*P*2*n).sum()/dias
print(f'\nReferencia: zona de ruido con base {BASE} MNQ ≈ ${tot:,.0f}/día (precio 27,000, sin costos)')
for X in (0.01,):
    l=np.minimum(dead,X)*P*2*n
    print(f'stop 1%: pérdida si el bot muere por tamaño -> ≤6 MNQ máx ${l[n<=6].max():,.0f} · 7–9 MNQ máx ${l[(n>6)&(n<=9)].max():,.0f} · 10–12 MNQ máx ${l[n>9].max():,.0f} · ops con >6 MNQ: {(n>6).mean()*100:.0f}%')
for B in (4500,4800):
    X=np.minimum(0.01, B/(2*n*P)); hit=mae>=X; ef=((-X-2/P)-res)[hit]*P*2*n[hit]; l=np.minimum(dead,X)*P*2*n
    print(f'min(1%, ${B}/(2·MNQ·precio)): salta {hit.sum()} ({hit.mean()*100:.1f}%) · efecto {ef.sum()/dias:+.2f} $/día · máx si muere ${l.max():,.0f}')
