import numpy as np, pandas as pd
T=pd.read_pickle('amplitud3.pkl'); W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]')
A11=pd.read_pickle('amplitud_trades.pkl')[['fecha','estr','lado','minuto','amp']].rename(columns={'amp':'amp11'})
T=T.merge(A11,on=['fecha','estr','lado','minuto'],how='left')
dias=W.index[(W.index>=T.fecha.min())&(W.index<=T.fecha.max())]
sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(z.cumsum()-z.cumsum().cummax()).min()
def rep(n,mult):
    z=(T.pnl*T.w*mult).groupby(T.fecha).sum().reindex(dias,fill_value=0); h=len(z)//2
    print(f"{n:<58} ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:h]):.2f}/{sh(z.iloc[h:]):.2f}) · caída ${dd(z):,.0f}")
rep('bot mejorado (sin amplitud)',1)
O=T.estr=='orb'
for n,mask in (('ORB fuera si amplitud de software ≤40%',O&(T.amp_software<=0.4)),('ORB medio si software ≤40%',None),
               ('ORB fuera si amplitud de 11 grandes ≤60%',O&(T.amp11<=0.6)),('ORB fuera si amplitud de 34 ≤60%',O&(T.amp<=0.6))):
    if mask is None: rep(n,np.where(O&(T.amp_software<=0.4),0.5,1)); continue
    a=T[mask]; b=T[O&~mask]; t=(a.pnl.mean()-b.pnl.mean())/np.sqrt(a.pnl.var()/len(a)+b.pnl.var()/len(b))
    rep(n+f' [t {t:.2f}]',np.where(mask,0,1))
