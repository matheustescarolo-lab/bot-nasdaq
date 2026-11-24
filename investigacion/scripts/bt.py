import numpy as np, pandas as pd
D = pd.read_csv(__import__('os').environ.get('ARCH','historia_ustec_m5.csv'), parse_dates=['ny']).set_index('ny')
POINT = 0.01
sp = D.spread.median() * POINT
dias = [(d, g) for d, g in D.groupby(D.index.date) if len(g) >= 70 and g.index[0].strftime('%H:%M') == '09:30']
print(f'{len(dias)} días completos · spread mediano {sp:.2f} puntos')
USD = 2.0                                    # US$ por punto (1 MNQ)
COSTO = (sp + 1.0) * USD                     # spread + 1 punto de deslizamiento, ida y vuelta, por operación

def orb(g, cierre_idx):
    o,h,l,c = g.o,g.h,g.l,g.c; hi, lo = h[:6].max(), l[:6].min()
    for i in range(6, cierre_idx+1):
        up, dn = h[i] > hi, l[i] < lo
        if up and dn: return []
        if up or dn:
            s = 1 if up else -1; st = lo if up else hi; e = max(hi, o[i]) if up else min(lo, o[i])
            if (s==1 and c[i] <= st) or (s==-1 and c[i] >= st): return [s*(st-e)]
            for j in range(i+1, cierre_idx+1):
                if (s==1 and l[j] <= st) or (s==-1 and h[j] >= st):
                    return [s*((min(st,o[j]) if s==1 else max(st,o[j]))-e)]
            return [s*(c[cierre_idx]-e)]
    return []

def ruido(g, hist, prev, cada=30, cierre_idx=76, tope_perdidas=None, filtro_orb=None):
    o,h,l,c,v = g.o,g.h,g.l,g.c,g.v; op=o[0]
    sig = np.array([np.mean([m[i] if len(m)>i else m[-1] for m in hist]) for i in range(len(c))])
    ub = max(op,prev)*(1+sig); lb = min(op,prev)*(1-sig)
    vw = np.cumsum((h+l+c)/3*v)/np.maximum(np.cumsum(v),1)
    pos=0; e=0; res=[]; perd=0
    for i in range(cierre_idx):
        fin = (i+1)*5 + 30 + 9*60                      # minutos desde medianoche al cierre de la vela
        if fin < 10*60 or fin % cada: continue
        old=pos
        if pos==1 and c[i] < max(ub[i],vw[i]): res.append(c[i]-e); pos=0
        elif pos==-1 and c[i] > min(lb[i],vw[i]): res.append(e-c[i]); pos=0
        if pos==0 and old!=0 and res[-1] < 0: perd+=1
        if pos==0 and (tope_perdidas is None or perd < tope_perdidas):
            s = 1 if c[i]>ub[i] else -1 if c[i]<lb[i] else 0
            if filtro_orb is not None and s != 0 and filtro_orb != 0 and s != filtro_orb: s = 0
            if s:
                if old==s:   # salir y volver a entrar del mismo lado = quedarse
                    e_old = res.pop(); pos=s; e = c[i] - (e_old if s==1 else -e_old)
                    if e_old<0: perd-=1
                else: pos=s; e=c[i]
    if pos: res.append(pos*(c[cierre_idx]-e))
    return res

def lado_orb(g):
    h,l=g.h,g.l; hi,lo=h[:6].max(),l[:6].min()
    for i in range(6,len(h)):
        if h[i]>hi and l[i]<lo: return 0
        if h[i]>hi: return 1
        if l[i]<lo: return -1
    return 0

class G: pass
arr=[]
for d,g in dias:
    idx = pd.date_range(pd.Timestamp(d)+pd.Timedelta(hours=9,minutes=30), periods=78, freq='5min')
    g = g.reindex(idx); g['close']=g.close.ffill(); g['tick_volume']=g.tick_volume.fillna(0)
    for k in ['open','high','low']: g[k]=g[k].fillna(g.close)
    x=G(); x.o,x.h,x.l,x.c,x.v = (g[k].values for k in ['open','high','low','close','tick_volume']); x.d=d; arr.append(x)
def corre(nombre, fn):
    pnl=[]; fechas=[]
    for k in range(14, len(arr)):
        hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
        r = fn(arr[k], hist, arr[k-1].c[-1])
        pnl.append(sum(x*USD - COSTO for x in r)); fechas.append(arr[k].d)
    s=pd.Series(pnl,index=pd.to_datetime(fechas)); m=len(s)//2
    sh=lambda z: z.mean()/z.std()*np.sqrt(252) if z.std()>0 else 0
    dd=(s.cumsum()-s.cumsum().cummax()).min()
    print(f'{nombre:<44} ${s.sum():>7,.0f} · ${s.mean():>5.1f}/día · Sharpe {sh(s):>5.2f} (1ª mitad {sh(s[:m]):>5.2f} · 2ª {sh(s[m:]):>5.2f}) · peor caída ${dd:,.0f}')
    return s
corre('ORB30 (cierre 15:55)', lambda g,h,p: orb(g,76))
corre('ORB30 (cierre 16:00, como el juez)', lambda g,h,p: orb(g,len(g.c)-1))
print()
corre('Ruido base: chequeo cada 30 min', lambda g,h,p: ruido(g,h,p,30))
corre('Ruido: chequeo cada 15 min', lambda g,h,p: ruido(g,h,p,15))
corre('Ruido: chequeo cada 60 min', lambda g,h,p: ruido(g,h,p,60))
corre('Ruido 30 min: para tras 1 pérdida en el día', lambda g,h,p: ruido(g,h,p,30,tope_perdidas=1))
corre('Ruido 30 min: para tras 2 pérdidas en el día', lambda g,h,p: ruido(g,h,p,30,tope_perdidas=2))
corre('Ruido 30 min: solo a favor del ORB', lambda g,h,p: ruido(g,h,p,30,filtro_orb=lado_orb(g)))
