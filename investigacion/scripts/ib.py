exec(open('reversa.py').read().split("fechas=[")[0])
def orb_n(g, nb, be=150, f=1.0):
    o,h,l,c = g.o,g.h,g.l,g.c; hi, lo = h[:nb].max(), l[:nb].min(); R=hi-lo
    for i in range(nb, CIERRE+1):
        up, dn = h[i] > hi, l[i] < lo
        if up and dn: return 0.0
        if up or dn:
            s = 1 if up else -1; e = max(hi, o[i]) if up else min(lo, o[i]); st = e - s*f*R
            if (s==1 and c[i] <= st) or (s==-1 and c[i] >= st): return s*(st-e)*USD-COSTO
            maxp = max(0,(c[i]-e)*s*USD)
            for j in range(i+1, CIERRE+1):
                x, maxp = gestiona(s, e, j, g, st, None, dict(tipo='be', activa=be), maxp)
                if x is not None: return s*(x-e)*USD-COSTO
            return s*(c[CIERRE]-e)*USD-COSTO
    return 0.0
fechas=[pd.Timestamp(g.d) for g in arr[20:]]; sh=lambda a: a.mean()/a.std()*np.sqrt(252); m=len(fechas)//2
for nb,nom in ((6,'30 min (el actual)'),(9,'45 min'),(12,'1 hora'),(18,'90 min')):
    for f in (0.5,1.0):
        z=pd.Series([orb_n(g,nb,150,f) for g in arr[20:]],index=fechas)
        print(f"rango de {nom}, stop {f}×: gana {(z[z!=0]>0).mean():.0%} · ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:m]):.2f}/{sh(z.iloc[m:]):.2f}) · corr con el bot {np.corrcoef(z.reindex(D.index).fillna(0),D.tot)[0,1]:+.2f}")
