import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
D=pd.read_pickle('flujo.pkl')
def sar(g, stop_mode='extremo', be=150, hasta=None):
    """Si el ORB se stopea (precio cruza el otro lado del rango), entra al revés. Stop en el extremo del día; break even; cierra al final."""
    o,h,l,c = g.o,g.h,g.l,g.c; hi, lo = h[:6].max(), l[:6].min(); R=hi-lo
    lado=0
    for i in range(6, CIERRE+1):
        up, dn = h[i] > hi, l[i] < lo
        if lado==0:
            if up and dn: return 0.0
            if up: lado=1
            elif dn: lado=-1
            continue
        if hasta and i>hasta: return 0.0
        # ¿cruzó el otro lado? (el ORB original se stopea)
        if (lado==1 and l[i] < lo) or (lado==-1 and h[i] > hi):
            s=-lado; e = min(lo,o[i]) if s==-1 else max(hi,o[i])
            ext = h[:i+1].max() if s==-1 else l[:i+1].min()
            st = ext if stop_mode=='extremo' else e - s*R
            if (s==1 and c[i] <= st) or (s==-1 and c[i] >= st): return s*(st-e)*USD-COSTO
            maxp=max(0,(c[i]-e)*s*USD)
            for j in range(i+1, CIERRE+1):
                x, maxp = gestiona(s, e, j, g, st, None, dict(tipo='be', activa=be), maxp)
                if x is not None: return s*(x-e)*USD-COSTO
            return s*(c[CIERRE]-e)*USD-COSTO
    return 0.0
fechas=[pd.Timestamp(g.d) for g in arr[20:]]
sh=lambda a: a.mean()/a.std()*np.sqrt(252); m=len(fechas)//2
for modo in ('extremo','rango'):
    for hasta in (None, 48, 30):
        z=pd.Series([sar(g,modo,150,hasta) for g in arr[20:]],index=fechas)
        n=(z!=0).sum(); comb=D.tot.add(z,fill_value=0).reindex(D.index)
        print(f"reversa (stop {modo}, entrada hasta {'cierre' if not hasta else f'{9.5+ (hasta+1)*5/60:.2f} h'}): {n} trades · gana {(z[z!=0]>0).mean():.0%} · ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:m]):.2f}/{sh(z.iloc[m:]):.2f}) · corr con el bot {np.corrcoef(z.reindex(D.index).fillna(0),D.tot)[0,1]:+.2f} · bot+reversa Sharpe {sh(comb):.2f} (bot solo {sh(D.tot):.2f})")
