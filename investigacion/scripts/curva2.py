import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
vol=pd.Series([np.mean([arr[j].h.max()-arr[j].l.min() for j in range(k-14,k)])/arr[k-1].c[-1] for k in range(20,len(arr))],index=[pd.Timestamp(arr[k].d) for k in range(20,len(arr))])
med=vol.rolling(250,min_periods=60).median().fillna(vol.expanding().median())
D=pd.read_pickle('flujo.pkl'); D['w']=np.clip(med/vol,0.5,1.5).reindex(D.index)
v=pd.read_csv('extra/vix_curva.csv',parse_dates=['fecha']).set_index('fecha'); v['r9']=v['^VIX9D']/v['^VIX']; v=v.shift(1)
X=D.join(v[['r9','^VIX']],how='inner').dropna(); m=len(X)//2
sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(z.cumsum()-z.cumsum().cummax()).min()
def rep(n,z): print(f'{n:<52} ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:m]):.2f}/{sh(z.iloc[m:]):.2f}) · caída ${dd(z):,.0f}')
B=X.tot*X.w; rep('Con tamaño por volatilidad (lo actual)',B)
for u in (1.05,1.08,1.1,1.12,1.15,1.2):
    s=X.r9>u; a=B[s]; b=B[~s]; t=(a.mean()-b.mean())/np.sqrt(a.var()/len(a)+b.var()/len(b))
    print(f'  VIX9D/VIX>{u}: {s.sum():3} días · ${a.mean():6.1f}/día vs ${b.mean():5.1f} · t {t:5.2f} · ORB {(X.orb*X.w)[s].mean():6.1f} · Ruido {(X.ru*X.w)[s].mean():6.1f} · % ganadores {(a>0).mean():.0%}')
for u in (1.1,1.15):
    rep(f'+ no operar si VIX9D/VIX>{u}', B.where(X.r9<=u,0)); rep(f'+ medio tamaño si VIX9D/VIX>{u}', B*np.where(X.r9>u,0.5,1))
s=X.r9>1.1; print('por año (días, $/día):', X[s].assign(b=B[s]).groupby(X[s].index.year).b.agg(['size','mean']).round(0).astype(int).T.to_dict())
print('VIX esos días:', X[s]['^VIX'].describe()[['min','50%','max']].round(1).to_dict())
print('hoy VIX9D/VIX =', round(26.70/25.46,3))
