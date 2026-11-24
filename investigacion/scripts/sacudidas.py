import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('escalones.py').read().split("print('ZONA DE RUIDO")[0])
RE=dict(tipo='esc',activa=200,paso=100); BE=dict(tipo='be',activa=150)
def shocks(g, umbral):
    r=np.abs(g.c/np.r_[g.o[0], g.c[:-1]]-1); return r>umbral
def orb_s(g, umbral, pausa, salir):
    o,h,l,c=g.o,g.h,g.l,g.c; hi,lo=h[:6].max(),l[:6].min(); sh=shocks(g,umbral) if umbral else np.zeros(78,bool)
    bloq=-1
    for i in range(6,CIERRE+1):
        if sh[i-1]: bloq=i-1+pausa
        up,dn=h[i]>hi,l[i]<lo
        if up and dn: return []
        if up or dn:
            if i<=bloq: return []                      # la ruptura llegó en la pausa: no entra ese día
            s=1 if up else -1; st=lo if up else hi; e=max(hi,o[i]) if up else min(lo,o[i])
            if (s==1 and c[i]<=st) or (s==-1 and c[i]>=st): return [s*(st-e)]
            maxp=max(0,(c[i]-e)*s*USD)
            for j in range(i+1,CIERRE+1):
                x,maxp=gestiona2(s,e,j,g,st,BE,maxp)
                if x is not None: return [s*(x-e)]
                if salir and sh[j] and s*(c[j]-c[j-1])<0: return [s*(c[j]-e)]   # sacudida en contra: sale al cierre de esa vela
            return [s*(c[CIERRE]-e)]
    return []
def ruido_s(g,hist,prev,umbral,pausa,salir):
    o,h,l,c,v=g.o,g.h,g.l,g.c,g.v; op=o[0]; sh=shocks(g,umbral) if umbral else np.zeros(78,bool)
    sig=np.array([np.mean([m[i] if len(m)>i else m[-1] for m in hist]) for i in range(len(c))])
    ub=max(op,prev)*(1+sig); lb=min(op,prev)*(1-sig); vw=np.cumsum((h+l+c)/3*v)/np.maximum(np.cumsum(v),1)
    pos=0;e=0;ie=0;res=[];maxp=0;bloq=-1
    for i in range(CIERRE):
        if sh[i]: bloq=i+pausa
        if pos and i>ie:
            x,maxp=gestiona2(pos,e,i,g,None,RE,maxp)
            if x is not None: res.append(pos*(x-e)); pos=0
            elif salir and sh[i] and pos*(c[i]-c[i-1])<0: res.append(pos*(c[i]-e)); pos=0
        fin=(i+1)*5+570
        if fin<600 or fin%30: continue
        old=pos
        if pos==1 and c[i]<max(ub[i],vw[i]): res.append(c[i]-e); pos=0
        elif pos==-1 and c[i]>min(lb[i],vw[i]): res.append(e-c[i]); pos=0
        if pos==0 and i>bloq:
            s=1 if c[i]>ub[i] else -1 if c[i]<lb[i] else 0
            if s and old==s: r=res.pop(); pos=s; e=c[i]-r if s==1 else c[i]+r
            elif s: pos,e,ie,maxp=s,c[i],i,0
    if pos: res.append(pos*(c[CIERRE]-e))
    return res
# ¿cuántas sacudidas hay?
tot=sum(shocks(arr[k],0.005).sum() for k in range(20,len(arr))); print(f'Velas de 5 min con movimiento >0.5%: {tot} en {len(arr)-20} días')
print('\nRANGO 30 MIN'); corre('Actual', lambda g,h,p: orb_s(g,None,0,False))
for u in (0.004,0.006,0.008):
    corre(f'Sacudida >{u:.1%}: pausa 30 min', lambda g,h,p,u=u: orb_s(g,u,6,False))
    corre(f'Sacudida >{u:.1%}: sale si es en contra', lambda g,h,p,u=u: orb_s(g,u,0,True))
print('\nZONA DE RUIDO'); corre('Actual', lambda g,h,p: ruido_s(g,h,p,None,0,False))
for u in (0.004,0.006,0.008):
    corre(f'Sacudida >{u:.1%}: pausa 30 min', lambda g,h,p,u=u: ruido_s(g,h,p,u,6,False))
    corre(f'Sacudida >{u:.1%}: sale si es en contra', lambda g,h,p,u=u: ruido_s(g,h,p,u,0,True))
