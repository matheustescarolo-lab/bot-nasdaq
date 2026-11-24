exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
import numpy as np
T={'orb':[], 'ruido':[]}; dias_con=0
for k in range(14,len(arr)):
    g=arr[k]; hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    a=[s*(x-e)*USD-COSTO for s,e,x,_,_ in orb_t(g)]; b=[s*(x-e)*USD-COSTO for s,e,x,_,_ in ruido_t(g,hist,arr[k-1].c[-1])]
    T['orb']+=a; T['ruido']+=b
n=len(arr)-14
for k,v in T.items():
    v=np.array(v); w=v[v>0]; l=v[v<=0]
    print(f"{k}: {len(v)} trades en {n} días ({len(v)/n:.1f}/día) · ganan {len(w)/len(v):.0%} · ganancia media +${w.mean():.0f} · pérdida media ${l.mean():.0f} · por trade ${v.mean():+.1f} · mejor +${v.max():.0f} · peor ${v.min():.0f}")
allv=np.array(T['orb']+T['ruido']); print(f"todas: por trade ${allv.mean():+.1f} · {len(allv)/n:.1f} trades/día · ${allv.sum()/n:.1f}/día")
