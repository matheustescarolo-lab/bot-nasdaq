import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
src=open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0]
G={}; exec(src,G); arr=G['arr']; USD=G['USD']
print('COSTO actual en la simulación:',G['COSTO'],'USD por trade por MNQ =',G['COSTO']/USD,'puntos')
sh=lambda z: z.mean()/z.std()*np.sqrt(252)
filas=[]
for k in range(20,len(arr)):
    g=arr[k]; hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    o=G['orb_t'](g); r=G['ruido_t'](g,hist,arr[k-1].c[-1])
    filas.append(dict(o=[s*(x-e)*USD for s,e,x,a,b in o], r=[s*(x-e)*USD for s,e,x,a,b in r]))
print('trades por día: ORB',np.mean([len(f['o']) for f in filas]).round(2),'· ruido',np.mean([len(f['r']) for f in filas]).round(2))
for co,cr in ((1,1),(3,1),(5,1),(5,2),(7,2),(5,3)):
    z=np.array([sum(p-co*USD for p in f['o'])+sum(p-cr*USD for p in f['r']) for f in filas]); m=len(z)//2
    print(f"costo ORB {co} pts, ruido {cr} pts por trade: ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z[:m]):.2f}/{sh(z[m:]):.2f})")
