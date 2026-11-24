import os, warnings, numpy as np, pandas as pd; warnings.filterwarnings('ignore')
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
C=np.load('caminos_C.npy'); W=np.load('caminos_W.npy')
fechas=pd.DatetimeIndex([pd.Timestamp(arr[k].d) for k in range(20,len(arr))]); pos={f:i for i,f in enumerate(fechas)}
R=pd.read_csv('reportes_gigantes.csv'); R['simbolo']=R.simbolo.replace({'GOOG':'GOOGL'}); R=R.drop_duplicates(['fecha','simbolo'])
R['fecha']=pd.to_datetime(R.fecha)
def reaccion(r):
    h=str(r.hora).lower()
    # el calendario histórico casi nunca trae la hora: todos estos reportan después del cierre salvo ASML (antes de la apertura)
    if 'pre' in h or (r.simbolo=='ASML' and 'after' not in h): d=r.fecha
    else: d=r.fecha+pd.Timedelta(days=1)
    i=fechas.searchsorted(d); return fechas[i] if i<len(fechas) else None
R['reaccion']=R.apply(reaccion,axis=1); R=R.dropna(subset=['reaccion'])
def dia(i, n=6, meta=1550):
    c=n*C[i]; w=n*W[i]
    for t in range(78):
        if c[t]>=meta: return c[t]
    return c[-1]
X=np.array([dia(i) for i in range(len(C))])
T=pd.read_pickle('trades8.pkl'); T['f']=T.fecha.dt.normalize()
def resumen(nombre, dias):
    idx=[pos[d] for d in dias if d in pos]
    if len(idx)<5: return
    x=X[idx]; o=np.delete(X, idx)
    t=(x.mean()-o.mean())/(x.std()/np.sqrt(len(x)))
    half=fechas[len(fechas)//2]; a=X[[i for i in idx if fechas[i]<half]].mean(); b=X[[i for i in idx if fechas[i]>=half]].mean()
    g=T[T.f.isin(set(dias))]
    print(f"{nombre:<34} {len(idx):>4} días · modo examen ${x.mean():+5.0f}/día (resto ${o.mean():+4.0f}) · t {t:4.1f} · (1ª ${a:+.0f} / 2ª ${b:+.0f}) · gana {np.mean(x>0):.0%} · meta {np.mean(x>=1550):.0%} · pierde>1k {np.mean(x<=-1000):.0%} · aciertos ORB {g[g.estr=='orb'].gana.mean():.0%} Ruido {g[g.estr=='ruido'].gana.mean():.0%}")
print(f"Día normal: ${X.mean():+.0f}/día · gana {np.mean(X>0):.0%} · meta {np.mean(X>=1550):.0%} · pierde>1k {np.mean(X<=-1000):.0%}\n")
resumen('Cualquier gigante (reacción)', set(R.reaccion))
top=['NVDA','MSFT','AAPL','AMZN','GOOGL','META','AVGO','TSLA']
resumen('Top 8 (NVDA MSFT AAPL AMZN GOOGL META AVGO TSLA)', set(R[R.simbolo.isin(top)].reaccion))
resumen('Resto (NFLX COST AMD PLTR ASML ADBE)', set(R[~R.simbolo.isin(top)].reaccion)-set(R[R.simbolo.isin(top)].reaccion))
print()
for s in top+['NFLX','AMD','ASML']:
    resumen(f'  {s}', set(R[R.simbolo==s].reaccion))
n_por_dia=R[R.simbolo.isin(top)].groupby('reaccion').size()
print()
resumen('Días con 2+ del top 8', set(n_por_dia[n_por_dia>=2].index))
