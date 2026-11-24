import numpy as np, pandas as pd
T=pd.read_pickle('factores_trades.pkl'); W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]')
T=T.join(W[['vol','r9','cot']],on='fecha'); T['w']=T.vol*T.r9*T.cot*np.where(T.gig,1.5,1)*np.where(T.nfp&(T.estr=='ruido'),1.5,1)
T['w']*=np.where(((T.estr=='ruido')&(T.ret1<-0.01))|((T.estr=='orb')&(T.ret1<-0.02)),0,1)
dias=W.index[(W.index>=T.fecha.min())&(W.index<=T.fecha.max())]
sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(z.cumsum()-z.cumsum().cummax()).min()
def rep(n,mult):
    z=(T.pnl*T.w*mult).groupby(T.fecha).sum().reindex(dias,fill_value=0); h=len(z)//2
    print(f"{n:<54} ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:h]):.2f}/{sh(z.iloc[h:]):.2f}) · caída ${dd(z):,.0f}")
rep('base nueva (capas + filtro de caída)',1)
R=T[T.estr=='ruido']
print('VIX 5 días (ruido, $/trade):', R.groupby(pd.cut(R.vix_5d,[-1,-0.15,-0.1,-0.05,0,0.05,0.1,1]),observed=True).pnl.agg(['mean','size']).round(1).T.to_dict())
print('cierre de ayer en su rango (ruido):', R.groupby(pd.cut(R.pos_ayer,[-0.01,0.2,0.4,0.6,0.8,1.01]),observed=True).pnl.agg(['mean','size']).round(1).T.to_dict())
for u in (-0.05,-0.1,-0.15):
    rep(f'ruido ×1.5 si el VIX bajó más de {-u:.0%} en 5 días', np.where((T.estr=='ruido')&(T.vix_5d<u),1.5,1))
for u in (0.7,0.8,0.9):
    rep(f'ruido ×1.5 si ayer cerró arriba del {u:.0%} de su rango', np.where((T.estr=='ruido')&(T.pos_ayer>u),1.5,1))
rep('ruido ×1.5 si las dos (VIX −10% y cierre >80%)', np.where((T.estr=='ruido')&(T.vix_5d<-0.1)&(T.pos_ayer>0.8),1.5,1))
print()
rep('ruido fuera si ayer cerró abajo del 20% de su rango', np.where((T.estr=='ruido')&(T.pos_ayer<0.2),0,1))
rep('ruido: fuera <20% y ×1.5 >80%', np.where(T.estr=='ruido',np.where(T.pos_ayer<0.2,0,np.where(T.pos_ayer>0.8,1.5,1)),1))
rep('ruido: medio <20% y ×1.5 >80%', np.where(T.estr=='ruido',np.where(T.pos_ayer<0.2,0.5,np.where(T.pos_ayer>0.8,1.5,1)),1))
O=T[T.estr=='orb']; print('ORB por cierre de ayer:', O.groupby(pd.cut(O.pos_ayer,[-0.01,0.2,0.4,0.6,0.8,1.01]),observed=True).pnl.mean().round(1).tolist())
m=T.fecha.quantile(0.5)
for a,b_ in ((-0.01,0.2),(0.8,1.01)):
    x=R[(R.pos_ayer>a)&(R.pos_ayer<=b_)]; print(f'ruido cierre {a}-{b_}: mitades ${x[x.fecha<m].pnl.mean():.1f} / ${x[x.fecha>=m].pnl.mean():.1f}')
