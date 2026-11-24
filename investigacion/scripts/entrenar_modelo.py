import os, sys, re, glob, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
sys.path.insert(0,'/home/claude/bot-nasdaq'); import rasgos as RG
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
cal=open('calendario.py').read(); FOMC=set(pd.to_datetime(re.search(r'FOMC="""(.*?)"""',cal,re.S).group(1).split()))
def d1(n):
    d=pd.read_csv(f'extra/{n}_d1.csv'); d['f']=pd.to_datetime(d.timestamp,unit='ms').dt.normalize(); return d.set_index('f').close
D1=pd.DataFrame({'spx':d1('usa500idxusd'),'usd':d1('dollaridxusd'),'bono':d1('ustbondtrusd')})
vx=pd.read_csv('extra/vix_curva.csv',parse_dates=['fecha']).set_index('fecha')['^VIX']; vx.index=vx.index.normalize()
F=RG.ctx_series(D1,vx)
H=pd.concat(pd.read_csv(f) for f in sorted(glob.glob('extra/nas_h1_*.csv')))
H.index=pd.to_datetime(H.timestamp,unit='ms',utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None); H=H.sort_index()
filas=[]
for k in range(25,len(arr)):
    g=arr[k]; f=pd.Timestamp(g.d); ctx=RG.ctx_dia(F,H,f)
    if ctx is None: continue
    base=RG.base_dia(arr[k-20:k],g); hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    trs=[('ruido',t) for t in ruido_t(g,hist,arr[k-1].c[-1])]
    if f not in FOMC: trs=[('orb',t) for t in orb_t(g)]+trs
    cnt={'orb':0,'ruido':0}
    for estr,(s,e,x,a,b) in trs:
        r=RG.rasgos_trade(base,ctx,estr,s,cnt[estr],a,e,g); cnt[estr]+=1
        r.update(fecha=f,estr=estr,pnl=s*(x-e)*USD-COSTO); filas.append(r)
T=pd.DataFrame(filas); T['gana']=(T.pnl>0).astype(int); T['año']=T.fecha.dt.year
print(len(T),'trades con rasgos ·',T.fecha.min().date(),'→',T.fecha.max().date()); T.to_pickle('modelo_trades.pkl')
from sklearn.linear_model import LogisticRegression; from sklearn.preprocessing import StandardScaler
def ajusta(tr):
    sc=StandardScaler().fit(tr[RG.FE]); lr=LogisticRegression(C=0.3,max_iter=3000).fit(sc.transform(tr[RG.FE]),tr.gana)
    p=lr.predict_proba(sc.transform(tr[RG.FE]))[:,1]
    return dict(media=sc.mean_.tolist(),escala=sc.scale_.tolist(),coef=lr.coef_[0].tolist(),intercepto=float(lr.intercept_[0]),corte=float(np.quantile(p,0.4)))
T['toma']=True; T['p']=np.nan
for estr in ('orb','ruido'):
    for y in range(2021,2027):
        tr=T[(T.estr==estr)&(T.año<y)]; te=(T.estr==estr)&(T.año==y)
        m=ajusta(tr); mod={'rasgos':RG.FE,estr:m}
        p=np.array([RG.probabilidad(mod,estr,row) for row in T.loc[te,RG.FE].to_dict('records')])
        T.loc[te,'p']=p; T.loc[te,'toma']=p>m['corte']
T.to_pickle('modelo_trades.pkl')
final={'rasgos':RG.FE,'entrenado_hasta':str(T.fecha.max().date()),'trades':int(len(T)),'nota':'regresión logística C=0.3; salta si prob <= corte (40% peor del entrenamiento)'}
for estr in ('orb','ruido'): final[estr]=ajusta(T[T.estr==estr])
json.dump(final,open('/home/claude/bot-nasdaq/modelo.json','w'),ensure_ascii=False,indent=1)
print('modelo.json guardado')
