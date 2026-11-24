import numpy as np, pandas as pd
T=pd.read_pickle('amplitud_trades.pkl'); W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]')
T['w']=T.vol*T.r9*T.cot*np.where(T.gig,1.5,1)*np.where(T.nfp&(T.estr=='ruido'),1.5,1)
dias=W.index[(W.index>=T.fecha.min())&(W.index<=T.fecha.max())]
sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(z.cumsum()-z.cumsum().cummax()).min()
def rep(n,mult):
    z=(T.pnl*T.w*mult).groupby(T.fecha).sum().reindex(dias,fill_value=0); h=len(z)//2
    print(f"{n:<56} ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:h]):.2f}/{sh(z.iloc[h:]):.2f}) · caída ${dd(z):,.0f}")
rep('Actual (todas las capas, sin amplitud)',1)
for u in (0.5,0.55,0.6,0.65,0.7):
    rep(f'Saltar si amplitud ≤ {u:.0%} (las dos estrategias)',np.where(T.amp<=u,0,1))
for u in (0.5,0.6,0.7):
    rep(f'Medio tamaño si amplitud ≤ {u:.0%}',np.where(T.amp<=u,0.5,1))
    rep(f'Saltar ≤{u:.0%} y ×1.5 si > 80%',np.where(T.amp<=u,0,np.where(T.amp>0.8,1.5,1)))
for e in ('orb','ruido'):
    D=T[T.estr==e]; lo=D[D.amp<=0.6]; hi=D[D.amp>0.6]
    print(f"{e}: amplitud ≤60% ${lo.pnl.mean():.1f}/trade ({len(lo)}) vs >60% ${hi.pnl.mean():.1f} ({len(hi)}) · t {(hi.pnl.mean()-lo.pnl.mean())/np.sqrt(hi.pnl.var()/len(hi)+lo.pnl.var()/len(lo)):.2f}")
print('por año, saltar ≤60%: ', {y:(round((g.pnl*g.w).sum()),round((g.pnl*g.w*np.where(g.amp<=0.6,0,1)).sum())) for y,g in T.groupby(T.fecha.dt.year)})
