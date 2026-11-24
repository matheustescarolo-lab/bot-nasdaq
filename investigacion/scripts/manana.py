import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
C=np.load('caminos_C.npy'); W=np.load('caminos_W.npy')
fechas=[arr[k].d for k in range(20,len(arr))]
ret=np.array([arr[k].c[-1]/arr[k-1].c[-1]-1 for k in range(20,len(arr))])          # retorno del día
ret_prev=np.array([arr[k-1].c[-1]/arr[k-2].c[-1]-1 for k in range(20,len(arr))])   # retorno del día anterior
hoy=arr[-1]; print('Hoy', hoy.d, f'· Nasdaq {hoy.c[-1]/arr[-2].c[-1]-1:+.2%} · rango del día {(hoy.h.max()-hoy.l.min()):.0f} puntos')
def dia(k, n=6, meta=1550):
    c=n*C[k]; w=n*W[k]; peor=0.0
    for t in range(78):
        peor=min(peor,w[t])
        if c[t]>=meta: return c[t], peor, t
    return c[-1], peor, 77
r_hoy=hoy.c[-1]/arr[-2].c[-1]-1
idx=[i for i in range(len(C)-1) if ret_prev[i] <= min(r_hoy*0.6, -0.007)]          # días que siguieron a una caída parecida
res=np.array([dia(i)[0] for i in idx]); peores=np.array([dia(i)[1] for i in idx])
tod=np.array([dia(i)[0] for i in range(len(C))])
print(f'\nDías parecidos (después de una caída de ~{r_hoy:.1%} o más): {len(idx)}')
for nombre,x in (('Después de caída',res),('Todos los días',tod)):
    print(f"{nombre:<18} promedio ${x.mean():+,.0f} · gana {np.mean(x>0):.0%} · llega a la meta +1,550 {np.mean(x>=1550):.0%} · pierde >$1,000 {np.mean(x<=-1000):.0%} · peor ${x.min():,.0f} · mejor ${x.max():,.0f}")
print('percentiles (después de caída):', {p: int(np.percentile(res,p)) for p in (10,25,50,75,90)})
rng=np.random.default_rng(int(pd.Timestamp('2026-11-18').value % 2**32))
pick=idx[rng.integers(len(idx))]; r,peor,t=dia(pick)
print(f'\nDía análogo sorteado: {fechas[pick]} (día anterior {ret_prev[pick]:+.1%}, ese día {ret[pick]:+.1%}) → bot ${r:+,.0f} · peor momento ${peor:,.0f} · {"meta a las "+str((9*60+35+5*t)//60)+":"+str((9*60+35+5*t)%60).zfill(2)+" NY" if r>=1550 else "cierre 15:55"}')
k=fechas.index(fechas[pick])+20
g=arr[k]; hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
for nombre, trs in (('Rango 30 min', orb_t(g)), ('Zona de ruido', ruido_t(g,hist,arr[k-1].c[-1]))):
    for s,e,x,a,b in trs:
        hm=lambda i: f"{(9*60+35+5*i)//60-1}:{str((9*60+35+5*i)%60).zfill(2)}"
        print(f"  {nombre}: {'compra' if s>0 else 'venta'} {hm(a)}→{hm(b)} (hora CDMX) · {6*(s*(x-e)*USD-COSTO):+,.0f} US$ con 6 MNQ")
