import sys, numpy as np, pandas as pd
ARCH = sys.argv[1]
src = open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0].replace("pd.read_csv('historia_ustec_m5.csv'", f"pd.read_csv('{ARCH}'")
exec(src)
# ---- variables conocidas ANTES de operar, por día ----
F=[]
for k in range(20, len(arr)):
    g=arr[k]; prev=arr[k-1]
    vol30=g.v[:6].sum(); vol30_h=np.mean([arr[j].v[:6].sum() for j in range(k-14,k)])
    cierres=[arr[j].c[-1] for j in range(k-20,k)]
    rangos=[arr[j].h.max()-arr[j].l.min() for j in range(k-14,k)]
    hi,lo=g.h[:6].max(), g.l[:6].min()
    F.append(dict(k=k, rvol=vol30/max(vol30_h,1), tend=np.sign(prev.c[-1]-np.mean(cierres)),
                  ancho=(hi-lo)/np.mean(rangos), gap=(g.o[0]/prev.c[-1]-1), cuerpo=np.sign(g.c[5]-g.o[0]),
                  vol14=np.mean(rangos)/prev.c[-1]))
F=pd.DataFrame(F)
res=[]
for _,f in F.iterrows():
    k=int(f.k); g=arr[k]; hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    to=orb_t(g); tr=ruido_t(g,hist,arr[k-1].c[-1])
    res.append(dict(orb=sum(s*(x-e)*USD-COSTO for s,e,x,_,_ in to), lado_orb=(to[0][0] if to else 0),
                    ruido=sum(s*(x-e)*USD-COSTO for s,e,x,_,_ in tr), lados_ru=[t[0] for t in tr], n_ru=len(tr)))
R=pd.concat([F.reset_index(drop=True), pd.DataFrame(res)],axis=1)
mitad=len(R)//2
sh=lambda z: z.mean()/z.std()*np.sqrt(252) if z.std()>0 else 0
def ver(nombre, col, mask):
    z=R[col].where(mask, 0.0)
    a,b=z[:mitad],z[mitad:]
    print(f'{nombre:<52} ${z.sum():>6,.0f} · ${z.mean():>5.1f}/día · Sharpe {sh(z):>5.2f} (1ª {sh(a):>5.2f} / 2ª {sh(b):>5.2f}) · opera {mask.mean():.0%} de los días')
print(f'{len(R)} días · {ARCH}')
print('— RANGO 30 MIN —')
ver('Base', 'orb', R.k>=0)
ver('Volumen de apertura alto (rvol > 1)', 'orb', R.rvol>1)
ver('Volumen de apertura bajo (rvol < 1)', 'orb', R.rvol<1)
ver('A favor de la tendencia de 20 días', 'orb', R.lado_orb==R.tend)
ver('En contra de la tendencia de 20 días', 'orb', (R.lado_orb!=R.tend)&(R.lado_orb!=0))
ver('Rango estrecho (ancho < mediana)', 'orb', R.ancho<R.ancho.median())
ver('Rango ancho (ancho > mediana)', 'orb', R.ancho>R.ancho.median())
ver('A favor del cuerpo de los primeros 30 min', 'orb', R.lado_orb==R.cuerpo)
ver('A favor del gap', 'orb', R.lado_orb==np.sign(R.gap))
ver('Días agitados (volatilidad 14 d > mediana)', 'orb', R.vol14>R.vol14.median())
print('— ZONA DE RUIDO —')
ver('Base', 'ruido', R.k>=0)
ver('Volumen de apertura alto (rvol > 1)', 'ruido', R.rvol>1)
ver('Días agitados (volatilidad 14 d > mediana)', 'ruido', R.vol14>R.vol14.median())
ver('Días tranquilos (volatilidad 14 d < mediana)', 'ruido', R.vol14<R.vol14.median())
ver('Gap grande (|gap| > mediana)', 'ruido', R.gap.abs()>R.gap.abs().median())
R.to_pickle(ARCH+'.pkl')
