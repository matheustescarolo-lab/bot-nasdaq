import numpy as np, pandas as pd
T=pd.read_pickle('factores_trades.pkl'); W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]')
T=T.join(W[['vol','r9','cot']],on='fecha'); T['w']=T.vol*T.r9*T.cot*np.where(T.gig,1.5,1)*np.where(T.nfp&(T.estr=='ruido'),1.5,1)
T['w']*=np.where(((T.estr=='ruido')&(T.ret1<-0.01))|((T.estr=='orb')&(T.ret1<-0.02)),0,1)
dias=W.index[(W.index>=T.fecha.min())&(W.index<=T.fecha.max())]
z=(T.pnl*T.w).groupby(T.fecha).sum().reindex(dias,fill_value=0)
prev=z.shift(1); prev5=z.rolling(5).sum().shift(1); racha=(z<0).astype(int).groupby((z>=0).cumsum()).cumsum().shift(1)
for n,mask in (('ayer el bot perdió',prev<0),('ayer el bot ganó',prev>0),('últimos 5 días negativos',prev5<0),('últimos 5 días positivos',prev5>0),('3+ días perdedores seguidos',racha>=3),('5+ seguidos',racha>=5)):
    a=z[mask]; b=z[~mask & prev.notna()]; t=(a.mean()-b.mean())/np.sqrt(a.var()/len(a)+b.var()/len(b)); h=len(z)//2
    print(f"{n:<28} {len(a):4} días · ${a.mean():6.1f}/día vs ${b.mean():5.1f} · t {t:5.2f} · mitades {z[mask].iloc[:0].size or ''}{a[a.index<z.index[h]].mean():.1f}/{a[a.index>=z.index[h]].mean():.1f}")
