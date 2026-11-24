exec(open('meseta.py').read().split("D=arr[20:]")[0])
D=arr[20:]; m=len(D)//2; sh=lambda a: a.mean()/a.std()*np.sqrt(252)
def orb_r(g, ber):
    o,h,l,c = g.o,g.h,g.l,g.c; hi, lo = h[:6].max(), l[:6].min(); R=hi-lo
    for i in range(6, CIERRE+1):
        up, dn = h[i] > hi, l[i] < lo
        if up and dn: return 0.0
        if up or dn:
            s = 1 if up else -1; e = max(hi, o[i]) if up else min(lo, o[i]); st = e - s*R
            if (s==1 and c[i] <= st) or (s==-1 and c[i] >= st): return s*(st-e)*USD-COSTO
            maxp = max(0,(c[i]-e)*s*USD); act=ber*R*USD
            for j in range(i+1, CIERRE+1):
                x, maxp = gestiona(s, e, j, g, st, None, dict(tipo='be', activa=act), maxp)
                if x is not None: return s*(x-e)*USD-COSTO
            return s*(c[CIERRE]-e)*USD-COSTO
    return 0.0
for ber in (0.2,0.3,0.4,0.5,0.6,0.75,1.0):
    z=np.array([orb_r(g,ber) for g in D])
    print(f"break even al ir +{ber:.2f}× el rango: ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z[:m]):.2f}/{sh(z[m:]):.2f})")
