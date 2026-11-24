import re, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
T=pd.read_pickle('modelo_trades.pkl'); T['fecha']=T.fecha.astype('datetime64[ns]')
T['pnl']=T.pnl-np.where(T.estr=='orb',0.5,1.0)*2.0             # costos realistas: ORB 1.5 pts (pendiente), ruido 2 pts
T['gana']=(T.pnl>0).astype(int)
cal=open('calendario.py').read(); grab=lambda n: set(pd.to_datetime(re.search(n+r'="""(.*?)"""',cal,re.S).group(1).split()))
FOMC,NFP,CPI=grab('FOMC'),grab('NFP'),grab('CPI')
bd=pd.offsets.BDay(1); f=T.fecha
T['dow']=f.dt.dayofweek; T['mes']=f.dt.month
T['cpi']=f.isin(CPI); T['nfp']=f.isin(NFP); T['pre_fomc']=f.isin([d-bd for d in FOMC]); T['post_fomc']=f.isin([d+bd for d in FOMC])
R=pd.read_csv('reportes_gigantes.csv',parse_dates=['fecha'])
for s in R.simbolo.unique():
    d=R[R.simbolo==s].fecha; T['post_'+s]=f.isin(list(d if s=='ASML' else d+bd))
T['gig']=T[[c for c in T if c.startswith('post_') and c!='post_fomc']].any(axis=1)
T['fin_trim']=T.fin_mes.astype(bool)&f.dt.month.isin([3,6,9,12])
m=T.fecha.quantile(0.5); sh=lambda z: z.mean()/z.std()*np.sqrt(252)
print(f"Base con costos realistas: ORB ${T[T.estr=='orb'].pnl.mean():.1f}/trade ({len(T[T.estr=='orb'])}) · ruido ${T[T.estr=='ruido'].pnl.mean():.1f}/trade ({len(T[T.estr=='ruido'])})")
res=[]
def prueba(nombre, mask):
    for e in ('orb','ruido'):
        D=T[T.estr==e]; a=D[mask[D.index]]; b=D[~mask[D.index]]
        if len(a)<25 or len(b)<25: continue
        t=(a.pnl.mean()-b.pnl.mean())/np.sqrt(a.pnl.var()/len(a)+b.pnl.var()/len(b))
        h1=a[a.fecha<m].pnl.mean()-b[b.fecha<m].pnl.mean(); h2=a[a.fecha>=m].pnl.mean()-b[b.fecha>=m].pnl.mean()
        res.append(dict(factor=nombre,estr=e,n=len(a),usd=a.pnl.mean(),resto=b.pnl.mean(),t=t,mitad1=h1,mitad2=h2,consistente=np.sign(h1)==np.sign(h2)))
for i,n in enumerate(['lunes','martes','miércoles','jueves','viernes']): prueba(n, T.dow==i)
for c in ('cpi','nfp','pre_fomc','post_fomc','gig','opex','fin_mes','fin_trim','nominas'): prueba(c, T[c].astype(bool))
for s in R.simbolo.unique(): prueba('después de '+s, T['post_'+s])
for c,qs in (('vix',None),('vix_rel',None),('vix_5d',None),('gap',None),('ret1',None),('ret5',None),('tend20',None),('vol14',None),('rvol',None),('ancho',None),('or_ret',None),('pos_ayer',None),('noc_rango',None),('noc_pos',None),('spx_tend',None),('dist_vwap',None),('mov_previo',None)):
    q=T[c].quantile([0.2,0.8])
    prueba(f'{c} bajo (20% inf.)', T[c]<=q.iloc[0]); prueba(f'{c} alto (20% sup.)', T[c]>=q.iloc[1])
for c in ('al_tend','al_gap','al_or','al_noc_ult3h','al_spx_1d','al_usd_5d','al_bono_5d'):
    prueba(f'{c} en contra', T[c]<0)
prueba('compras',T.lado==1); prueba('2ª entrada o más del día',T.n_previas>=1)
for a,b_ in ((600,660),(660,780),(780,900),(900,960)): prueba(f'entrada {a//60}:{a%60:02d}–{b_//60}:{b_%60:02d}',(T.minuto+570>=a)&(T.minuto+570<b_))
X=pd.DataFrame(res); X['abs_t']=X.t.abs()
fuertes=X[(X.abs_t>=2.5)&X.consistente].sort_values('t')
print(f'\n{len(X)} pruebas. Con |t|≥2.5 y mismo signo en las dos mitades ({len(fuertes)}):'); print(fuertes.round(2).to_string(index=False))
print('\nCasi (2.0≤|t|<2.5, consistentes):'); print(X[(X.abs_t>=2.0)&(X.abs_t<2.5)&X.consistente].sort_values('t').round(2).to_string(index=False))
X.to_pickle('factores.pkl'); T.to_pickle('factores_trades.pkl')
