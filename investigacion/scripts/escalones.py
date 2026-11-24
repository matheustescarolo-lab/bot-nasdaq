import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('bt2.py').read().split("print('RANGO 30 MIN")[0])
def gestiona2(s, e, j, g, stop, regla, maxp):
    o,h,l = g.o[j], g.h[j], g.l[j]; piso=None
    if regla and maxp >= regla['activa']:
        if regla['tipo']=='be': piso=0.0
        else:
            p=regla['paso']; piso=(maxp//p)*p - p*regla.get('atras',1)
            if regla.get('be_antes') is not None: piso=max(piso, 0.0)
        if regla.get('be') is not None and maxp>=regla['be']: piso=max(piso if piso is not None else 0.0, 0.0)
    niv=[x for x in (stop, None if piso is None else e+s*piso/USD) if x is not None]
    if niv:
        m=max(niv) if s==1 else min(niv)
        if (s==1 and l<=m) or (s==-1 and h>=m): return (min(m,o) if s==1 else max(m,o)), maxp
    return None, max(maxp, (h-e)*USD if s==1 else (e-l)*USD)
def orb2(g, regla):
    o,h,l,c=g.o,g.h,g.l,g.c; hi,lo=h[:6].max(),l[:6].min()
    for i in range(6,CIERRE+1):
        up,dn=h[i]>hi,l[i]<lo
        if up and dn: return []
        if up or dn:
            s=1 if up else -1; st=lo if up else hi; e=max(hi,o[i]) if up else min(lo,o[i])
            if (s==1 and c[i]<=st) or (s==-1 and c[i]>=st): return [s*(st-e)]
            maxp=max(0,(c[i]-e)*s*USD)
            for j in range(i+1,CIERRE+1):
                x,maxp=gestiona2(s,e,j,g,st,regla,maxp)
                if x is not None: return [s*(x-e)]
            return [s*(c[CIERRE]-e)]
    return []
def ruido2(g,hist,prev,regla):
    o,h,l,c,v=g.o,g.h,g.l,g.c,g.v; op=o[0]
    sig=np.array([np.mean([m[i] if len(m)>i else m[-1] for m in hist]) for i in range(len(c))])
    ub=max(op,prev)*(1+sig); lb=min(op,prev)*(1-sig); vw=np.cumsum((h+l+c)/3*v)/np.maximum(np.cumsum(v),1)
    pos=0;e=0;ie=0;res=[];maxp=0
    for i in range(CIERRE):
        if pos and i>ie:
            x,maxp=gestiona2(pos,e,i,g,None,regla,maxp)
            if x is not None: res.append(pos*(x-e)); pos=0
        fin=(i+1)*5+570
        if fin<600 or fin%30: continue
        old=pos
        if pos==1 and c[i]<max(ub[i],vw[i]): res.append(c[i]-e); pos=0
        elif pos==-1 and c[i]>min(lb[i],vw[i]): res.append(e-c[i]); pos=0
        if pos==0:
            s=1 if c[i]>ub[i] else -1 if c[i]<lb[i] else 0
            if s and old==s: r=res.pop(); pos=s; e=c[i]-r if s==1 else c[i]+r
            elif s: pos,e,ie,maxp=s,c[i],i,0
    if pos: res.append(pos*(c[CIERRE]-e))
    return res
def corre(nombre, fn):
    out=[];f=[]
    for k in range(20,len(arr)):
        hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
        out.append(sum(x*USD-COSTO for x in fn(arr[k],hist,arr[k-1].c[-1]))); f.append(arr[k].d)
    s=pd.Series(out,index=pd.to_datetime(f)); m=len(s)//2
    sh=lambda z:z.mean()/z.std()*np.sqrt(252)
    print(f'{nombre:<58} ${s.mean():5.1f}/día · Sharpe {sh(s):.2f} ({sh(s[:m]):.2f}/{sh(s[m:]):.2f}) · caída ${(s.cumsum()-s.cumsum().cummax()).min():,.0f}')
print('ZONA DE RUIDO (por 1 MNQ; con 6 MNQ multiplica los US$ ×6)')
corre('Actual: desde +$200, escalones de $100', lambda g,h,p: ruido2(g,h,p,dict(tipo='esc',activa=200,paso=100)))
for a,pa in [(150,50),(100,50),(100,25),(60,20),(200,50),(300,50)]:
    corre(f'Desde +${a}, escalones de ${pa}', lambda g,h,p,a=a,pa=pa: ruido2(g,h,p,dict(tipo='esc',activa=a,paso=pa)))
print('\nRANGO 30 MIN')
corre('Actual: break even a +$150', lambda g,h,p: orb2(g,dict(tipo='be',activa=150)))
for a,pa in [(200,100),(200,50),(300,100),(400,100)]:
    corre(f'Break even a +$150 y escalera desde +${a}, escalones de ${pa}', lambda g,h,p,a=a,pa=pa: orb2(g,dict(tipo='esc',activa=a,paso=pa,be=150)))
