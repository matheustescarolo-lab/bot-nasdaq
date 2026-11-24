import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
def pnl(trs): 
    L=sum(s*(x-e)*USD-COSTO for s,e,x,a,b in trs if s==1); S=sum(s*(x-e)*USD-COSTO for s,e,x,a,b in trs if s==-1); return L,S
R=[]
for k in range(20,len(arr)):
    g=arr[k]; hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    oL,oS=pnl(orb_t(g)); rL,rS=pnl(ruido_t(g,hist,arr[k-1].c[-1]))
    R.append(dict(fecha=pd.Timestamp(g.d), oL=oL,oS=oS,rL=rL,rS=rS, ret=g.c[-1]/arr[k-1].c[-1]-1, rango=(g.h.max()-g.l.min())/g.o[0]))
R=pd.DataFrame(R).set_index('fecha'); R['orb']=R.oL+R.oS; R['ru']=R.rL+R.rS; R['tot']=R.orb+R.ru
x=pd.read_csv('extra/dix_gex.csv',parse_dates=['date']).set_index('date')
x['gex_pct']=x.gex.rolling(250,min_periods=120).rank(pct=True); x['dix_pct']=x.dix.rolling(250,min_periods=120).rank(pct=True)
x=x.shift(1)                                     # solo lo que se conoce antes de abrir
D=R.join(x[['gex','dix','gex_pct','dix_pct']],how='inner').dropna()
print(len(D),'días', D.index.min().date(), D.index.max().date())
sh=lambda z: z.mean()/z.std()*np.sqrt(252) if len(z)>5 else np.nan
D['q']=pd.qcut(D.gex_pct,4,labels=['GEX muy bajo','bajo','alto','GEX muy alto'])
print('\n== Gamma de los dealers (día anterior) vs. nuestras estrategias ($/día, 1 MNQ c/u)')
print(D.groupby('q',observed=True).agg(dias=('tot','size'),orb=('orb','mean'),ruido=('ru','mean'),total=('tot','mean'),rango_pct=('rango',lambda z:z.mean()*100)).round(1))
print('GEX negativo:', D[D.gex<0].tot.agg(['size','mean']).round(1).to_dict(), '| positivo:', D[D.gex>=0].tot.agg(['size','mean']).round(1).to_dict())
D['qd']=pd.qcut(D.dix_pct,4,labels=['DIX muy bajo','bajo','alto','DIX muy alto'])
print('\n== Compra en dark pools (DIX día anterior): largos vs cortos ($/día)')
print(D.groupby('qd',observed=True).agg(dias=('tot','size'),largos=('oL',lambda z:(z+D.loc[z.index,'rL']).mean()),cortos=('oS',lambda z:(z+D.loc[z.index,'rS']).mean()),nasdaq_dia=('ret',lambda z:z.mean()*1e4)).round(1))
# mitades
m=len(D)//2
for n,a in (('1a mitad',D.iloc[:m]),('2a mitad',D.iloc[m:])):
    print(n, a.groupby('q',observed=True).tot.mean().round(1).to_dict())
D.to_pickle('flujo.pkl')
