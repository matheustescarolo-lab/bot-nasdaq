import numpy as np, pandas as pd
exec(open('bt.py').read().split("corre('ORB30 (cierre 15:55)'")[0].replace("print(f'{len(dias)}","pass #"))
CIERRE = 76

def gestiona(s, e, j, g, stop, tp, regla, maxp):
    """Revisa la vela j para una posición abierta. Devuelve (precio de salida o None, maxp). Primero lo malo (conservador)."""
    o,h,l = g.o[j], g.h[j], g.l[j]
    piso = None
    if regla and maxp >= regla['activa']:
        if regla['tipo'] == 'trailing': piso = maxp - regla['dist']
        elif regla['tipo'] == 'be': piso = regla.get('colchon', 0)
        elif regla['tipo'] == 'escalera': piso = (maxp // 100) * 100 - 100
    niveles = []                                     # precios de salida por el lado malo
    if stop is not None: niveles.append(stop)
    if piso is not None: niveles.append(e + s * piso / USD)
    if niveles:
        malo = max(niveles) if s == 1 else min(niveles)
        if (s == 1 and l <= malo) or (s == -1 and h >= malo):
            return (min(malo, o) if s == 1 else max(malo, o)), maxp
    if tp is not None and ((s == 1 and h >= tp) or (s == -1 and l <= tp)):
        return (max(tp, o) if s == 1 else min(tp, o)), maxp
    maxp = max(maxp, (h - e) * USD if s == 1 else (e - l) * USD)
    return None, maxp

def orb_g(g, tpR=None, regla=None):
    o,h,l,c = g.o,g.h,g.l,g.c; hi, lo = h[:6].max(), l[:6].min()
    for i in range(6, CIERRE+1):
        up, dn = h[i] > hi, l[i] < lo
        if up and dn: return []
        if up or dn:
            s = 1 if up else -1; st = lo if up else hi; e = max(hi, o[i]) if up else min(lo, o[i])
            if (s==1 and c[i] <= st) or (s==-1 and c[i] >= st): return [s*(st-e)]
            tp = e + s*tpR*abs(e-st) if tpR else None
            maxp = max(0, (c[i]-e)*s*USD)
            for j in range(i+1, CIERRE+1):
                x, maxp = gestiona(s, e, j, g, st, tp, regla, maxp)
                if x is not None: return [s*(x-e)]
            return [s*(c[CIERRE]-e)]
    return []

def ruido_g(g, hist, prev, tp_usd=None, regla=None, cada=30):
    o,h,l,c,v = g.o,g.h,g.l,g.c,g.v; op=o[0]
    sig = np.array([np.mean([m[i] if len(m)>i else m[-1] for m in hist]) for i in range(len(c))])
    ub = max(op,prev)*(1+sig); lb = min(op,prev)*(1-sig)
    vw = np.cumsum((h+l+c)/3*v)/np.maximum(np.cumsum(v),1)
    pos=0; e=0; res=[]; maxp=0
    for i in range(CIERRE):
        if pos and i > ie:
            tp = e + pos*tp_usd/USD if tp_usd else None
            x, maxp = gestiona(pos, e, i, g, None, tp, regla, maxp)
            if x is not None: res.append(pos*(x-e)); pos=0
        fin = (i+1)*5 + 570
        if fin < 600 or fin % cada: continue
        old=pos
        if pos==1 and c[i] < max(ub[i],vw[i]): res.append(c[i]-e); pos=0
        elif pos==-1 and c[i] > min(lb[i],vw[i]): res.append(e-c[i]); pos=0
        if pos==0:
            s = 1 if c[i]>ub[i] else -1 if c[i]<lb[i] else 0
            if s:
                if old==s:
                    r=res.pop(); pos=s; e = c[i]-r if s==1 else c[i]+r
                else: pos=s; e=c[i]; ie=i; maxp=0
    if pos: res.append(pos*(c[CIERRE]-e))
    return res

R = {}
def corre(nombre, fn):
    pnl=[]; f=[]
    for k in range(14, len(arr)):
        hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
        pnl.append(sum(x*USD - COSTO for x in fn(arr[k], hist, arr[k-1].c[-1]))); f.append(arr[k].d)
    s=pd.Series(pnl,index=pd.to_datetime(f)); m=len(s)//2
    sh=lambda z: z.mean()/z.std()*np.sqrt(252) if z.std()>0 else 0
    dd=(s.cumsum()-s.cumsum().cummax()).min()
    print(f'{nombre:<46} ${s.sum():>7,.0f} · Sharpe {sh(s):>5.2f} ({sh(s[:m]):>5.2f} / {sh(s[m:]):>5.2f}) · caída ${dd:,.0f}')
    R[nombre]=s

print('RANGO 30 MIN                                   total     Sharpe (1ª / 2ª mitad)')
corre('Base (stop en el otro lado, sin objetivo)', lambda g,h,p: orb_g(g))
for t in (1, 1.5, 2, 3): corre(f'Take profit {t}:1', lambda g,h,p,t=t: orb_g(g, tpR=t))
corre('Break even al ir +$200', lambda g,h,p: orb_g(g, regla=dict(tipo='be', activa=200)))
corre('Escalera: a +$200 asegura $100, sube de $100', lambda g,h,p: orb_g(g, regla=dict(tipo='escalera', activa=200)))
for d in (200, 400): corre(f'Trailing ${d} desde +$200', lambda g,h,p,d=d: orb_g(g, regla=dict(tipo='trailing', activa=200, dist=d)))
print('\nZONA DE RUIDO')
corre('Base (sale solo por la regla de la zona)', lambda g,h,p: ruido_g(g,h,p))
for t in (200, 300, 500): corre(f'Take profit ${t}', lambda g,h,p,t=t: ruido_g(g,h,p,tp_usd=t))
corre('Break even al ir +$200', lambda g,h,p: ruido_g(g,h,p,regla=dict(tipo='be', activa=200)))
corre('Escalera: a +$200 asegura $100, sube de $100', lambda g,h,p: ruido_g(g,h,p,regla=dict(tipo='escalera', activa=200)))
for d in (200, 400): corre(f'Trailing ${d} desde +$200', lambda g,h,p,d=d: ruido_g(g,h,p,regla=dict(tipo='trailing', activa=200, dist=d)))
