import numpy as np, pandas as pd
D=pd.read_pickle('flujo.pkl'); c=pd.read_csv('extra/cot_nasdaq.csv',low_memory=False,parse_dates=['Report_Date_as_YYYY-MM-DD'])
c=c[c.Market_and_Exchange_Names.str.contains('Consolidated')].copy() if (c.Market_and_Exchange_Names.str.contains('Consolidated').sum()>300) else c
c=c.groupby('Report_Date_as_YYYY-MM-DD')[['Lev_Money_Positions_Long_All','Lev_Money_Positions_Short_All','Asset_Mgr_Positions_Long_All','Asset_Mgr_Positions_Short_All','Open_Interest_All']].sum().sort_index()
c['lev']=(c.iloc[:,0]-c.iloc[:,1])/c.Open_Interest_All; c['am']=(c.iloc[:,2]-c.iloc[:,3])/c.Open_Interest_All
c['dlev']=c.lev.diff(); c['zlev']=(c.lev-c.lev.rolling(52).mean())/c.lev.rolling(52).std()
c.index=c.index+pd.Timedelta(days=6)                 # martes -> lunes siguiente (se publica el viernes)
X=pd.merge_asof(D.sort_index(),c[['lev','dlev','zlev','am']].dropna(),left_index=True,right_index=True)
X=X.dropna(subset=['zlev']); L=X.oL+X.rL; S=X.oS+X.rS
for col in ('dlev','zlev'):
    X['q']=pd.qcut(X[col],4,labels=['muy bajo','bajo','alto','muy alto'])
    g=X.groupby('q',observed=True); print(f'\n{col} (fondos apalancados, {len(X)} días):'); print(pd.DataFrame({'largos':g.apply(lambda a:(a.oL+a.rL).mean()),'cortos':g.apply(lambda a:(a.oS+a.rS).mean()),'nasdaq_pb':g.ret.mean()*1e4,'total':g.tot.mean()}).round(1))
print('\n=== robustez dlev')
X['q']=pd.qcut(X.dlev,4,labels=['muy bajo','bajo','alto','muy alto']); X['adl']=X.dlev.abs()
m=len(X)//2
for n,a in (('1a mitad',X.iloc[:m]),('2a mitad',X.iloc[m:])): print(n, a.groupby('q',observed=True).tot.mean().round(1).to_dict())
# semanas independientes: t-stat a nivel semana
X['sem']=X.index.to_period('W'); W=X.groupby('sem').agg(tot=('tot','sum'),dlev=('dlev','first'))
r=np.corrcoef(W.dlev,W.tot)[0,1]; print('semanas',len(W),'corr',round(r,3),'t≈',round(r*np.sqrt(len(W)-2)/np.sqrt(1-r*r),2))
a=W[W.dlev>W.dlev.quantile(.75)].tot; b=W[W.dlev<=W.dlev.quantile(.25)].tot
print('t (cuartil alto vs bajo, semanas):', round((a.mean()-b.mean())/np.sqrt(a.var()/len(a)+b.var()/len(b)),2))
print(X.groupby([X.index.year,'q'],observed=True).tot.mean().unstack().round(0))
X['qa']=pd.qcut(X.adl,4,labels=['q1','q2','q3','q4']); print('|cambio|:',X.groupby('qa',observed=True).tot.mean().round(1).to_dict())
sh=lambda z: z.mean()/z.std()*np.sqrt(252)
for w,n in ((np.where(X.q=='muy bajo',0.5,1),'medio tamaño si fondos recortaron fuerte'),(np.where(X.q=='muy bajo',0,1),'no operar esa semana')):
    z=X.tot*w; print(n, f'${z.mean():.1f}/día Sharpe {sh(z):.2f} ({sh(z.iloc[:m]):.2f}/{sh(z.iloc[m:]):.2f}) vs base {sh(X.tot):.2f} ({sh(X.tot.iloc[:m]):.2f}/{sh(X.tot.iloc[m:]):.2f})')
