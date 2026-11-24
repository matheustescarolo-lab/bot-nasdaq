import numpy as np, pandas as pd, glob, os
T=pd.read_pickle('modelo_trades.pkl'); W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]')
T['fecha']=T.fecha.astype('datetime64[ns]'); T=T.join(W,on='fecha'); T['a']=(T.minuto/5-1).astype(int)
PES={'nvda':9,'msft':8,'aapl':8,'amzn':5.5,'googl':5,'avgo':5,'fb':4,'tsla':3,'cost':2.5,'nflx':2,'amd':1.5}   # pesos aproximados en el Nasdaq-100
slots=pd.timedelta_range('09:30:00','15:55:00',freq='5min')
R={}
for f in sorted(glob.glob('extra/acciones/*.csv.gz')):
    s=os.path.basename(f).split('ususd')[0]; d=pd.read_csv(f,parse_dates=['ny']); d['dia']=d.ny.dt.normalize(); d['t']=d.ny-d.dia
    piv_c=d.pivot_table(index='dia',columns='t',values='close').reindex(columns=slots).ffill(axis=1)
    op=d.groupby('dia').open.first()
    R[s]=(piv_c.sub(op,axis=0)).div(op,axis=0)                    # retorno desde la apertura al cierre de cada vela
print('acciones:',list(R), '· días', len(next(iter(R.values()))))
def amplitud(fecha, bar, lado, pesado=False):
    num=den=0.0
    for s,M in R.items():
        if fecha not in M.index or bar<0: continue
        r=M.at[fecha,slots[bar]]
        if np.isnan(r): continue
        w=PES[s] if pesado else 1.0
        num+=w*(np.sign(r)==lado); den+=w
    return num/den if den else np.nan
T['amp']=[amplitud(f,(a-1 if e=='orb' else a),l) for f,a,e,l in zip(T.fecha,T.a,T.estr,T.lado)]
T['ampw']=[amplitud(f,(a-1 if e=='orb' else a),l,True) for f,a,e,l in zip(T.fecha,T.a,T.estr,T.lado)]
T=T.dropna(subset=['amp']); m=T.fecha.quantile(0.5)
for col,nom in (('amp','igual peso'),('ampw','por peso en el índice')):
    print(f'\nAmplitud a favor del trade ({nom}) — US$/trade por grupo (1ª mitad / 2ª mitad):')
    for e in ('orb','ruido'):
        D=T[T.estr==e]; D['g']=pd.cut(D[col],[-0.01,0.4,0.6,0.8,1.01],labels=['≤40%','40–60%','60–80%','>80%'])
        tab=D.groupby('g',observed=True).agg(n=('pnl','size'),usd=('pnl','mean'),gana=('gana','mean'))
        tab['1a']=D[D.fecha<m].groupby('g',observed=True).pnl.mean(); tab['2a']=D[D.fecha>=m].groupby('g',observed=True).pnl.mean()
        print(e); print(tab.round(2).to_string())
T.to_pickle('amplitud_trades.pkl')
