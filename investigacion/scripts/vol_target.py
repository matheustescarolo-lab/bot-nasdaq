import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
C=np.load('caminos_C.npy'); fin=C[:,-1]
f=[arr[k].d for k in range(20,len(arr))]
vol=np.array([np.mean([arr[j].h.max()-arr[j].l.min() for j in range(k-14,k)])/arr[k-1].c[-1] for k in range(20,len(arr))])
sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(np.cumsum(z)-np.maximum.accumulate(np.cumsum(z))).min()
m=len(fin)//2
def rep(n,z): print(f'{n:<52} ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z[:m]):.2f}/{sh(z[m:]):.2f}) · caída ${dd(z):,.0f}')
rep('Tamaño fijo (1 MNQ c/u)', fin)
for lo,hi in ((0.5,1.5),(0.5,2.0),(0.33,3.0)):
    w=np.clip(np.median(vol)/vol, lo, hi); w=w/w.mean()            # mismo tamaño promedio
    rep(f'Tamaño según volatilidad (de {lo}× a {hi}×)', fin*w)
w=np.clip(vol/np.median(vol),0.5,2.0); w=w/w.mean(); rep('Al revés: más tamaño cuando hay más volatilidad', fin*w)
