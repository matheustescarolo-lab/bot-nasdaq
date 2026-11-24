import numpy as np, pandas as pd
R=pd.read_pickle('div.pkl'); T=pd.DataFrame({k:v.orb+v.ru for k,v in R.items()}).dropna(); m=len(T)//2
sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(z.cumsum()-z.cumsum().cummax()).min()
def rep(n,z): print(f'{n:<34} ${z.mean():6.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:m]):.2f}/{sh(z.iloc[m:]):.2f}) · caída ${dd(z):,.0f} · peor día ${z.min():,.0f}')
print('Cada mercado solo (ORB + Ruido, 1 MNQ-equivalente c/u):')
for k in T: rep(k,T[k]); 
for k in T: print(f'   {k}: ORB {R[k].orb.mean():.1f} (Sharpe {sh(R[k].orb):.2f}) · Ruido {R[k].ru.mean():.1f} (Sharpe {sh(R[k].ru):.2f})')
print('\nCorrelación diaria de resultados:'); print(T.corr().round(2))
print('\nCombinaciones (mismo riesgo total: se reparte el tamaño):')
for combo in (['NQ'],['NQ','ES'],['NQ','YM'],['NQ','ORO'],['NQ','ES','ORO'],['NQ','ES','YM','ORO']):
    rep(' + '.join(combo)+' (repartido)', T[combo].mean(axis=1))
print('\nSumando sin repartir (más riesgo):')
for combo in (['NQ','ORO'],['NQ','ES','ORO']): rep(' + '.join(combo), T[combo].sum(axis=1))
print('\nPor año $/día:'); print(T.groupby(T.index.year).mean().round(0).astype(int).T)
