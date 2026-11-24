import numpy as np, pandas as pd, glob, os
T=pd.read_pickle('factores_trades.pkl'); W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]')
T=T.join(W[['vol','r9','cot']],on='fecha'); T['a']=(T.minuto/5-1).astype(int)
T['w']=T.vol*T.r9*T.cot*np.where(T.gig,1.5,1)*np.where(T.nfp&(T.estr=='ruido'),1.5,1)
T['w']*=np.where(((T.estr=='ruido')&(T.ret1<-0.01))|((T.estr=='orb')&(T.ret1<-0.02)),0,1)
T['w']*=np.where(T.estr=='ruido',np.where(T.pos_ayer<0.2,0.5,np.where(T.pos_ayer>0.8,1.5,1)),1)
SEC={'semis':['nvda','avgo','amd','qcom','txn','intc','amat','mu','lrcx','adi'],'software':['msft','googl','fb','adbe','intu','nflx'],
     'consumo':['amzn','tsla','cost','pep','sbux','mdlz','orly','mar','cmcsa'],'salud':['amgn','isrg','gild','vrtx','regn'],'otros':['aapl','csco','hon','pypl']}
slots=pd.timedelta_range('09:30:00','15:55:00',freq='5min'); RET={}
for f in sorted(glob.glob('extra/acciones/*.csv.gz')):
    s=os.path.basename(f).split('ususd')[0]; d=pd.read_csv(f,parse_dates=['ny']); d['dia']=d.ny.dt.normalize(); d['t']=d.ny-d.dia
    pc=d.pivot_table(index='dia',columns='t',values='close').reindex(columns=slots).ffill(axis=1); op=d.groupby('dia').open.first()
    RET[s]=pc.sub(op,axis=0).div(op,axis=0)
print(len(RET),'acciones')
def amp(fecha,bar,lado,grupo=None):
    v=[np.sign(RET[s].at[fecha,slots[bar]])==lado for s in (grupo or RET) if s in RET and fecha in RET[s].index and bar>=0 and not np.isnan(RET[s].at[fecha,slots[bar]])]
    return np.mean(v) if v else np.nan
bar=np.where(T.estr=='orb',T.a-1,T.a)
T['amp']=[amp(f,b,l) for f,b,l in zip(T.fecha,bar,T.lado)]
for k,g in SEC.items(): T['amp_'+k]=[amp(f,b,l,g) for f,b,l in zip(T.fecha,bar,T.lado)]
T=T.dropna(subset=['amp']); T.to_pickle('amplitud3.pkl'); m=T.fecha.quantile(0.5)
for col in ['amp']+['amp_'+k for k in SEC]:
    print(f'\n{col} — US$/trade (1ª/2ª mitad):')
    for e in ('orb','ruido'):
        D=T[T.estr==e]; g=pd.cut(D[col],[-0.01,0.4,0.6,0.8,1.01],labels=['≤40','40–60','60–80','>80'])
        r=D.groupby(g,observed=True).pnl.agg(['mean','size']); r['m1']=D[D.fecha<m].groupby(g[D.fecha<m],observed=True).pnl.mean(); r['m2']=D[D.fecha>=m].groupby(g[D.fecha>=m],observed=True).pnl.mean()
        print(' ',e,' | '.join(f"{i}: ${row['mean']:.1f} ({row['m1']:.0f}/{row['m2']:.0f}) n{int(row['size'])}" for i,row in r.iterrows()))
