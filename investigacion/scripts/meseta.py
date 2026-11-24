import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
def orb_p(g, f, tpR, be=150):
    o,h,l,c = g.o,g.h,g.l,g.c; hi, lo = h[:6].max(), l[:6].min(); R=hi-lo
    for i in range(6, CIERRE+1):
        up, dn = h[i] > hi, l[i] < lo
        if up and dn: return None
        if up or dn:
            s = 1 if up else -1; e = max(hi, o[i]) if up else min(lo, o[i]); st = e - s*f*R
            if (s==1 and l[i] <= st) or (s==-1 and h[i] >= st): return s*(st-e)*USD-COSTO
            tp = e + s*tpR*f*R if tpR else None
            maxp = max(0,(c[i]-e)*s*USD)
            for j in range(i+1, CIERRE+1):
                x, maxp = gestiona(s, e, j, g, st, tp, dict(tipo='be', activa=be), maxp)
                if x is not None: return s*(x-e)*USD-COSTO
            return s*(c[CIERRE]-e)*USD-COSTO
    return None
D=arr[20:]; m=len(D)//2
F=[0.25,0.35,0.5,0.65,0.8,1.0]; TP=[1,1.5,2,3,4,None]
res={}
for f in F:
    for tp in TP:
        z=np.array([orb_p(g,f,tp) or 0.0 for g in D])
        sh=lambda a: a.mean()/a.std()*np.sqrt(252)
        res[(f,tp)]=(z.mean(), sh(z), sh(z[:m]), sh(z[m:]), z.min(), np.percentile(z,1))
print('Sharpe ORB (1 MNQ, con break even +150) — filas: stop = fracción del rango · columnas: objetivo en múltiplos del stop')
print('stop\\obj '+''.join(f'{str(t):>18}' for t in TP))
for f in F: print(f'{f:<9}'+''.join(f"{res[(f,t)][1]:6.2f} ({res[(f,t)][2]:.2f}/{res[(f,t)][3]:.2f})" for t in TP))
print('\n$/día y peor día:')
for f in F: print(f'{f:<9}'+''.join(f"  ${res[(f,t)][0]:5.1f} / {res[(f,t)][4]:6.0f}" for t in TP))
pd.to_pickle(res,'meseta.pkl')
