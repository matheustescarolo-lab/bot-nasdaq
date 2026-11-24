import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
G={}; exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0],G); arr=G['arr']; USD=G['USD']; CI=G['CIERRE']; gest=G['gestiona']
def orb_v(g, modo, desl):
    """modo 'mercado': entra desl puntos después del nivel (bot actual, revisando cada 10 s).
       modo 'pendiente': orden stop en el nivel (+desl de deslizamiento); si la vela toca los dos lados, cuenta como pérdida."""
    o,h,l,c = g.o,g.h,g.l,g.c; hi, lo = h[:6].max(), l[:6].min()
    for i in range(6, CI+1):
        up, dn = h[i] > hi, l[i] < lo
        if up and dn:
            if modo=='mercado': return None
            s=1 if abs(o[i]-hi)<abs(o[i]-lo) else -1                 # el lado más cercano a la apertura de la vela se llena primero
            e=(max(hi,o[i]) if s==1 else min(lo,o[i]))+s*desl; st=lo if s==1 else hi
            return s*(st-e)*USD-1*USD
        if up or dn:
            s = 1 if up else -1; st = lo if up else hi
            e = (max(hi, o[i]) if up else min(lo, o[i])) + s*desl
            if (s==1 and c[i] <= st) or (s==-1 and c[i] >= st): return s*(st-e)*USD-1*USD
            maxp = max(0,(c[i]-e)*s*USD)
            for j in range(i+1, CI+1):
                x, maxp = gest(s, e, j, g, st, None, dict(tipo='be', activa=150), maxp)
                if x is not None: return s*(x-e)*USD-1*USD
            return s*(c[CI]-e)*USD-1*USD
    return None
sh=lambda z: z.mean()/z.std()*np.sqrt(252); D=arr[20:]; m=len(D)//2
for modo,desl in (('mercado',0),('mercado',2),('mercado',4),('mercado',6),('pendiente',0),('pendiente',0.5),('pendiente',1)):
    z=np.array([orb_v(g,modo,desl) or 0.0 for g in D]); n=sum(1 for g in D if orb_v(g,modo,desl) is not None)
    print(f"ORB {modo:<9} deslizamiento {desl} pts (+1 pt de spread): ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z[:m]):.2f}/{sh(z[m:]):.2f}) · trades {n}")
amb=sum(1 for g in D if any((g.h[i]>g.h[:6].max()) and (g.l[i]<g.l[:6].min()) for i in range(6,7)))
print('días con vela que rompe los dos lados en la primera vela tras el rango:',amb)
