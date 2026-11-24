import numpy as np, pandas as pd
D=pd.read_pickle('flujo.pkl'); v=pd.read_csv('extra/vix_curva.csv',parse_dates=['fecha']).set_index('fecha')
v['ratio']=v['^VIX']/v['^VIX3M']; v['r9']=v['^VIX9D']/v['^VIX']; v=v.shift(1)          # cierre de ayer
X=D.join(v[['ratio','r9','^VIX']],how='inner').dropna(); m=len(X)//2
sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(z.cumsum()-z.cumsum().cummax()).min()
for col,cortes in (('ratio',[0,0.85,0.9,0.95,1.0,9]),('r9',[0,0.9,1.0,1.1,9])):
    X['q']=pd.cut(X[col],cortes); g=X.groupby('q',observed=True)
    print(f'\n{col}:'); print(pd.DataFrame({'dias':g.size(),'orb':g.orb.mean(),'ruido':g.ru.mean(),'total':g.tot.mean(),'1a':X.iloc[:m].groupby('q',observed=True).tot.mean(),'2a':X.iloc[m:].groupby('q',observed=True).tot.mean()}).round(1))
def rep(n,z): print(f'{n:<44} ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:m]):.2f}/{sh(z.iloc[m:]):.2f}) · caída ${dd(z):,.0f}')
rep('base',X.tot)
for u in (0.95,1.0):
    for w in (0.5,1.5):
        rep(f'tamaño {w}× si VIX/VIX3M > {u}', X.tot*np.where(X.ratio>u,w,1))
inv=X[X.ratio>1]; a=inv.tot; b=X[X.ratio<=1].tot; print('t invertida vs normal', round((a.mean()-b.mean())/np.sqrt(a.var()/len(a)+b.var()/len(b)),2))
print('invertida por año:', inv.groupby(inv.index.year).tot.agg(['size','mean']).round(0).T.to_dict())
