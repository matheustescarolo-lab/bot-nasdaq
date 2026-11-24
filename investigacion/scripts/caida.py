import numpy as np, pandas as pd
T=pd.read_pickle('factores_trades.pkl'); W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]')
T=T.join(W[['vol','r9','cot']],on='fecha')
T['w']=T.vol*T.r9*T.cot*np.where(T.gig,1.5,1)*np.where(T.nfp&(T.estr=='ruido'),1.5,1)
print('Retorno de ayer (cierre a cierre) por tramos — US$/trade:')
T['tramo']=pd.cut(T.ret1,[-1,-0.02,-0.012,-0.006,0,0.006,0.012,0.02,1])
print(T.pivot_table(index='tramo',columns='estr',values='pnl',aggfunc=['mean','size'],observed=True).round(1))
m=T.fecha.quantile(0.5)
for u in (-0.006,-0.01,-0.012,-0.015,-0.02):
    a=T[T.ret1<u]; print(f"ayer < {u:.1%}: {a.fecha.nunique()} días · ORB ${a[a.estr=='orb'].pnl.mean():.1f} ({a[(a.estr=='orb')&(a.fecha<m)].pnl.mean():.1f}/{a[(a.estr=='orb')&(a.fecha>=m)].pnl.mean():.1f}) · ruido ${a[a.estr=='ruido'].pnl.mean():.1f} ({a[(a.estr=='ruido')&(a.fecha<m)].pnl.mean():.1f}/{a[(a.estr=='ruido')&(a.fecha>=m)].pnl.mean():.1f}) · con VIX9D>1.1 ya recortado: {(a.r9<1).mean():.0%}")
dias=W.index[(W.index>=T.fecha.min())&(W.index<=T.fecha.max())]
sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(z.cumsum()-z.cumsum().cummax()).min()
def rep(n,mult):
    z=(T.pnl*T.w*mult).groupby(T.fecha).sum().reindex(dias,fill_value=0); h=len(z)//2
    print(f"{n:<52} ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:h]):.2f}/{sh(z.iloc[h:]):.2f}) · caída ${dd(z):,.0f}")
print('\nSobre todas las capas actuales, costos realistas:')
rep('actual',1)
for u in (-0.01,-0.012,-0.015,-0.02):
    rep(f'ayer < {u:.1%}: no operar', np.where(T.ret1<u,0,1))
    rep(f'ayer < {u:.1%}: medio tamaño', np.where(T.ret1<u,0.5,1))
    rep(f'ayer < {u:.1%}: no operar la zona de ruido', np.where((T.ret1<u)&(T.estr=='ruido'),0,1))
print()
for ur,uo in ((-0.01,-0.02),(-0.012,-0.02),(-0.01,-0.015),(-0.008,-0.02)):
    rep(f'ruido fuera si ayer < {ur:.1%}, ORB fuera si < {uo:.1%}', np.where(((T.estr=='ruido')&(T.ret1<ur))|((T.estr=='orb')&(T.ret1<uo)),0,1))
