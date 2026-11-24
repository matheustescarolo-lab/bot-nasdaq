import numpy as np, pandas as pd
D=pd.read_pickle('flujo.pkl'); sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(z.cumsum()-z.cumsum().cummax()).min()
L=D.oL+D.rL; S=D.oS+D.rS; m=len(D)//2
def rep(n,z): print(f'{n:<50} ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:m]):.2f}/{sh(z.iloc[m:]):.2f}) · caída ${dd(z):,.0f}')
rep('Todo (base)', D.tot)
for lo,hi in ((0.25,0.75),(0.2,0.8),(0.1,0.9),(0.33,0.67)):
    z=L.where(D.dix_pct>lo,0)+S.where(D.dix_pct<hi,0)
    rep(f'Sin largos si DIX<{lo:.0%} · sin cortos si DIX>{hi:.0%}', z)
# medio tamaño en lugar de saltar
z=L*np.where(D.dix_pct<=0.25,0.5,1)+S*np.where(D.dix_pct>=0.75,0.5,1); rep('Medio tamaño en contra del DIX (25/75)', z)
# por año
D['z']=L.where(D.dix_pct>0.25,0)+S.where(D.dix_pct<0.75,0)
print((D.groupby(D.index.year)[['tot','z']].sum()).round(0).astype(int).T)
# t-stat de la diferencia largo-corto por cuartil
for q in ('DIX muy bajo','DIX muy alto'):
    a=D[D.qd==q]; d=(a.oL+a.rL)-(a.oS+a.rS); print(q,'largos−cortos t =',round(d.mean()/d.std()*np.sqrt(len(d)),2))
# señal pura: retorno del Nasdaq al día siguiente según DIX
print('Nasdaq día siguiente (pb) por cuartil DIX:', D.groupby('qd',observed=True).ret.mean().mul(1e4).round(1).to_dict())
