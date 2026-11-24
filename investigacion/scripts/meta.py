import os, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
filas=[]
for k in range(25, len(arr)):
    g=arr[k]; p=arr[k-1]; hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    pc=p.c[-1]; cierres=np.array([arr[j].c[-1] for j in range(k-20,k)])
    rango_med=np.mean([arr[j].h.max()-arr[j].l.min() for j in range(k-14,k)])
    vol30=g.v[:6].sum(); vol30m=np.mean([arr[j].v[:6].sum() for j in range(k-14,k)])
    vw=np.cumsum((g.h+g.l+g.c)/3*g.v)/np.maximum(np.cumsum(g.v),1)
    base=dict(fecha=pd.Timestamp(g.d), gap=g.o[0]/pc-1, ret1=pc/arr[k-2].c[-1]-1, ret5=pc/arr[k-6].c[-1]-1,
              tend20=pc/cierres.mean()-1, vol14=rango_med/pc, rvol=vol30/max(vol30m,1), ancho=(g.h[:6].max()-g.l[:6].min())/rango_med,
              or_ret=g.c[5]/g.o[0]-1, dow=pd.Timestamp(g.d).dayofweek,
              pos_ayer=(pc-p.l.min())/max(p.h.max()-p.l.min(),1e-9))
    for estr, trs in (('orb', orb_t(g)), ('ruido', ruido_t(g,hist,pc))):
        for n,(s,e,x,a,b) in enumerate(trs):
            f=dict(base); f.update(estr=estr, lado=s, n_previas=n, minuto=a*5+5,
                   al_tend=s*np.sign(f['tend20']), al_gap=s*np.sign(f['gap']), al_or=s*np.sign(f['or_ret']),
                   dist_vwap=s*(e-vw[a])/e, mov_previo=s*(g.c[a]/g.o[0]-1),
                   pnl=s*(x-e)*USD-COSTO)
            filas.append(f)
T=pd.DataFrame(filas); T['gana']=(T.pnl>0).astype(int); T['año']=T.fecha.dt.year
T.to_pickle('trades8.pkl')
print(T.groupby('estr').agg(n=('pnl','size'), gana=('gana','mean'), usd=('pnl','mean')).round(3))
