import glob, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
T=pd.read_pickle('trades8.pkl')
def d1(nombre):
    df=pd.read_csv(f'extra/{nombre}_d1.csv'); df['f']=pd.to_datetime(df.timestamp,unit='ms').dt.normalize()
    return df.set_index('f').close
ctx=pd.DataFrame({'spx':d1('usa500idxusd'),'vix':d1('volidxusd'),'usd':d1('dollaridxusd'),'bono':d1('ustbondtrusd')}).ffill()
F=pd.DataFrame(index=ctx.index)
F['vix']=ctx.vix; F['vix_rel']=ctx.vix/ctx.vix.rolling(20).mean()-1; F['vix_5d']=ctx.vix.pct_change(5)
F['spx_1d']=ctx.spx.pct_change(); F['spx_tend']=ctx.spx/ctx.spx.rolling(50).mean()-1
F['usd_5d']=ctx.usd.pct_change(5); F['bono_5d']=ctx.bono.pct_change(5)
F=F.shift(1)            # solo lo que ya se conocía al abrir: datos hasta el día anterior
# sesión nocturna (h1, hora de Nueva York): de las 16:00 de ayer a las 9:30 de hoy
H=pd.concat(pd.read_csv(f) for f in sorted(glob.glob('extra/nas_h1_*.csv')))
H['ny']=pd.to_datetime(H.timestamp,unit='ms',utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None)
H=H.set_index('ny').sort_index()
noc={}
for d in T.fecha.dt.normalize().unique():
    d=pd.Timestamp(d); w=H[(H.index>=d-pd.Timedelta(hours=8))&(H.index<d+pd.Timedelta(hours=9))]   # 16:00 de ayer → 9:00 de hoy
    if len(w)<8: continue
    rng=w.high.max()-w.low.min(); ult=w.close.iloc[-1]
    noc[d]=dict(noc_rango=rng/ult, noc_pos=(ult-w.low.min())/max(rng,1e-9), noc_ult3h=ult/w.close.iloc[-4]-1)
N=pd.DataFrame(noc).T
T['f']=T.fecha.dt.normalize()
T=T.join(F,on='f').join(N,on='f')
# calendario: nóminas (primer viernes), vencimiento mensual de opciones (tercer viernes), último día del mes
d=T.fecha
T['nominas']=((d.dt.dayofweek==4)&(d.dt.day<=7)).astype(int)
T['opex']=((d.dt.dayofweek==4)&(d.dt.day>=15)&(d.dt.day<=21)).astype(int)
T['fin_mes']=(d+pd.offsets.BDay(1)).dt.month.ne(d.dt.month).astype(int)
for c in ['vix_5d','spx_1d','spx_tend','usd_5d','bono_5d','noc_ult3h']:
    T['al_'+c]=T.lado*np.sign(T[c])
T['al_noc_pos']=T.lado*(T.noc_pos-0.5)
T=T.dropna(subset=['vix','noc_rango'])
T.to_pickle('trades8x.pkl'); print(len(T),'trades con todo el contexto')
# ¿qué variable sola separa mejor ganadores de perdedores? (diferencia de US$ por trade entre mitades, en las dos mitades del tiempo)
mit=T.fecha.quantile(0.5)
print(f"\n{'variable':<14} {'estr':<6} {'1ª mitad: arriba-abajo US$/trade':>34} {'2ª mitad':>10}")
for e in ('orb','ruido'):
    D=T[T.estr==e]
    for c in ['vix','vix_rel','vix_5d','spx_tend','noc_rango','noc_pos','al_noc_pos','al_noc_ult3h','al_spx_1d','al_vix_5d','al_usd_5d','al_bono_5d','nominas','opex','fin_mes']:
        r=[]
        for parte in (D[D.fecha<mit], D[D.fecha>=mit]):
            med=parte[c].median()
            hi=parte[parte[c]>med].pnl.mean(); lo=parte[parte[c]<=med].pnl.mean()
            r.append(hi-lo)
        marca='  ✅ consistente' if np.sign(r[0])==np.sign(r[1]) and min(abs(r[0]),abs(r[1]))>8 else ''
        print(f'{c:<14} {e:<6} {r[0]:>34.1f} {r[1]:>10.1f}{marca}')
