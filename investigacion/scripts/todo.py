import os, re, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
cal=open('calendario.py').read(); grab=lambda n: set(pd.to_datetime(re.search(n+r'="""(.*?)"""',cal,re.S).group(1).split()))
FOMC,NFP=grab('FOMC'),grab('NFP')
# ---- trades con las reglas actuales
rows=[]
for k in range(20,len(arr)):
    g=arr[k]; f=pd.Timestamp(g.d); hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    if f not in FOMC:
        for s,e,x,a,b in orb_t(g): rows.append(dict(fecha=f,estr='orb',lado=s,minuto=(a+1)*5,pnl=s*(x-e)*USD-COSTO))
    for s,e,x,a,b in ruido_t(g,hist,arr[k-1].c[-1]): rows.append(dict(fecha=f,estr='ruido',lado=s,minuto=(a+1)*5,pnl=s*(x-e)*USD-COSTO))
T=pd.DataFrame(rows); T['fecha']=T.fecha.astype('datetime64[ns]'); dias=pd.DatetimeIndex([pd.Timestamp(arr[k].d) for k in range(20,len(arr))]).astype('datetime64[ns]')
# ---- pesos diarios
vol=pd.Series([np.mean([arr[j].h.max()-arr[j].l.min() for j in range(k-14,k)])/arr[k-1].c[-1] for k in range(20,len(arr))],index=dias)
med=vol.rolling(250,min_periods=60).median().fillna(vol.expanding().median()); W=pd.DataFrame(index=dias)
W['vol']=np.clip(med/vol,0.5,1.5)
v=pd.read_csv('extra/vix_curva.csv',parse_dates=['fecha']).set_index('fecha'); W['r9']=np.where((v['^VIX9D']/v['^VIX']).shift(1).reindex(dias)>1.10,0.5,1.0)
c=pd.read_csv('extra/cot_nasdaq.csv',low_memory=False,parse_dates=['Report_Date_as_YYYY-MM-DD']); c=c[c.Market_and_Exchange_Names.str.contains('Consolidated')]
c['Report_Date_as_YYYY-MM-DD']=c['Report_Date_as_YYYY-MM-DD'].astype('datetime64[ns]'); c=c.groupby('Report_Date_as_YYYY-MM-DD')[['Lev_Money_Positions_Long_All','Lev_Money_Positions_Short_All','Open_Interest_All']].sum().sort_index()
c['dlev']=((c.iloc[:,0]-c.iloc[:,1])/c.Open_Interest_All).diff(); c.index=c.index+pd.Timedelta(days=6)
W['cot']=np.where(pd.merge_asof(pd.DataFrame(index=dias),c[['dlev']].dropna(),left_index=True,right_index=True).dlev<-0.0259,0.5,1.0)
R=pd.read_csv('reportes_gigantes.csv',parse_dates=['fecha']); bd=pd.offsets.BDay(1)
gig=set((R[R.simbolo!='ASML'].fecha+bd))|set(R[R.simbolo=='ASML'].fecha); nv=set(R[R.simbolo=='NVDA'].fecha+bd)
W['gig']=dias.isin(list(gig)); W['nvda']=dias.isin(list(nv)); W['nfp']=dias.isin(list(NFP))
T=T.join(W,on='fecha')
# ---- modelo con contexto (rasgos de trades8x) a prueba fuera de muestra 2024–2026
X8=pd.read_pickle('trades8x.pkl').fillna(0.0); X8['fecha']=X8.fecha.dt.normalize().astype('datetime64[ns]')
FE=['vix','vix_rel','vix_5d','spx_tend','noc_rango','noc_pos','al_noc_pos','al_noc_ult3h','al_spx_1d','al_usd_5d','al_bono_5d','nominas','opex','fin_mes','gap','ret1','ret5','tend20','vol14','rvol','ancho','or_ret','pos_ayer','lado','n_previas','minuto','al_tend','al_gap','al_or','dist_vwap','mov_previo']
M=T.merge(X8[['fecha','estr','lado','minuto']+[f for f in FE if f not in ('lado','minuto')]],on=['fecha','estr','lado','minuto'],how='left')
print(f"trades con rasgos del modelo: {M.vix.notna().mean():.0%} (desde 2022-10: {M[M.fecha>='2022-10-06'].vix.notna().mean():.0%})")
from sklearn.linear_model import LogisticRegression; from sklearn.preprocessing import StandardScaler; from sklearn.pipeline import make_pipeline
M['toma']=True
for e in ('orb','ruido'):
    for y in (2024,2025,2026):
        tr=M[(M.estr==e)&(M.fecha.dt.year<y)&M.vix.notna()]; te=(M.estr==e)&(M.fecha.dt.year==y)&M.vix.notna()
        mdl=make_pipeline(StandardScaler(),LogisticRegression(C=0.3,max_iter=2000)).fit(tr[FE],tr.pnl>0)
        corte=np.quantile(mdl.predict_proba(tr[FE])[:,1],0.4); M.loc[te,'toma']=mdl.predict_proba(M.loc[te,FE])[:,1]>corte
M.to_pickle('todo_trades.pkl'); W.to_pickle('todo_pesos.pkl')
sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(z.cumsum()-z.cumsum().cummax()).min()
def serie(wfun, filtro=None, desde=None):
    t=M if filtro is None else M[filtro]
    z=(t.pnl*wfun(t)).groupby(t.fecha).sum().reindex(dias,fill_value=0)
    return z[z.index>=desde] if desde else z
def rep(n,z):
    h=len(z)//2; print(f"{n:<58} ${z.mean():6.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:h]):.2f}/{sh(z.iloc[h:]):.2f}) · caída ${dd(z):,.0f}")
capas=lambda t: t.vol*t.r9
for desde,titulo in ((None,'2019–2026 (todo)'),('2024-01-01','2024–2026 (donde se puede probar el modelo)')):
    print(f'\n=== {titulo} · 1 MNQ base')
    rep('Actual: volatilidad + VIX9D',serie(capas,None,desde))
    rep('+ COT medio tamaño',serie(lambda t: capas(t)*t.cot,None,desde))
    for E in (1.5,2.0): rep(f'+ ×{E} el día después de reportes de gigantes',serie(lambda t,E=E: capas(t)*np.where(t.gig,E,1),None,desde))
    rep('+ ×2 solo el día después de Nvidia',serie(lambda t: capas(t)*np.where(t.nvda,2,1),None,desde))
    rep('+ ×1.5 zona de ruido en días de NFP',serie(lambda t: capas(t)*np.where(t.nfp&(t.estr=='ruido'),1.5,1),None,desde))
    if desde: rep('+ modelo con contexto (salta 40% peor)',serie(capas,M.toma,desde))
    rep('TODO junto (COT + gigantes ×1.5 + NFP ruido ×1.5' + (' + modelo)' if desde else ')'),
        serie(lambda t: capas(t)*t.cot*np.where(t.gig,1.5,1)*np.where(t.nfp&(t.estr=='ruido'),1.5,1), M.toma if desde else None, desde))
