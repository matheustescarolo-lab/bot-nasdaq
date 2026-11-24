import numpy as np, pandas as pd, re
x=pd.read_csv('/home/claude/bot-nasdaq/historia_nas_dukascopy.csv',parse_dates=['ny']).set_index('ny')
x=x[(x.index.time>=pd.Timestamp('09:30').time())&(x.index.time<pd.Timestamp('16:00').time())]
D={d:v for d,v in x.groupby(x.index.date) if len(v)==78}
cal=open('calendario.py').read(); FOMC=set(pd.to_datetime(re.search(r'FOMC="""(.*?)"""',cal,re.S).group(1).split()).date)
USD=2.0; COSTO=3.0; CIERRE=76; ULTIMA_ENTRADA=66   # 15:00
def setup(o,h,l,c,lado,nivel_fn,objetivo_fn,R_obj=None):
    """Trampa de ruptura (BPR) del lado 'lado' (+1: rompe el máximo y vendemos; -1: rompe el mínimo y compramos)."""
    # espejo para usar la misma lógica: trabajamos siempre como "rompe máximo → venta"
    if lado==-1: o,h,l,c=-o,-l,-h,-c
    nivel=nivel_fn(o,h,l,c)
    for b in range(6,CIERRE):                       # primera vela que rompe el máximo
        if h[b]>nivel: break
    else: return None
    prev_min=l[max(0,b-6):b].min()                   # «mínimo anterior» (30 min antes de romper)
    # FVG alcista dentro de la subida: l[i] > h[i-2], con i entre b-6 y el pico
    estado=None; pico=b; bull=None
    for j in range(b+1,CIERRE):
        if h[j]>h[pico]: pico=j
        # FVG alcista que contiene la ruptura (formado hasta el pico)
        if bull is None:
            for i in range(max(2,b-6),pico+1):
                if l[i]>h[i-2]: bull=(h[i-2],l[i])
        # FVG bajista después del pico que se cruza con el alcista → BPR
        if bull and j>=pico+2 and h[j]<l[j-2]:
            bear=(h[j],l[j-2]); lo_=max(bull[0],bear[0]); hi_=min(bull[1],bear[1])
            if hi_>lo_: estado=('bpr',lo_,hi_,j)
        if estado and c[j]<prev_min:                 # quiebre de estructura: CIERRA debajo del mínimo anterior
            _,lo_,hi_,jb=estado; ent=(lo_+hi_)/2; stop=h[pico]+0.5; obj=objetivo_fn(o,h,l,c,j,ent,stop)
            for k in range(j+1,ULTIMA_ENTRADA+1):    # espera que el precio vuelva a la mitad del BPR
                if h[k]>=stop: return None           # se fue arriba antes de llenar
                if h[k]>=ent:
                    for m in range(k,CIERRE+1):
                        if h[m]>=stop: return -(stop-ent)*USD-COSTO, k
                        if m>k and l[m]<=obj: return (ent-obj)*USD-COSTO, k
                    return (ent-c[CIERRE])*USD-COSTO, k
            return None
    return None
niv_orb=lambda o,h,l,c: h[:6].max()
obj_orb=lambda o,h,l,c,j,ent,stop: min(l[:6].min(), l[:j+1].min())          # objetivo: mínimo del rango / del día (liquidez)
obj_2r=lambda o,h,l,c,j,ent,stop: ent-2*(stop-ent)
res=[]
for d in sorted(D):
    if d in FOMC: continue
    v=D[d]; o,h,l,c=(v[k].values for k in ('open','high','low','close'))
    for nom,objf in (('liquidez',obj_orb),('2R',obj_2r)):
        for lado in (1,-1):
            r=setup(o,h,l,c,lado,niv_orb,objf)
            if r: res.append(dict(fecha=d,objetivo=nom,lado=lado,pnl=r[0],vela=r[1]))
R=pd.DataFrame(res); n_dias=len([d for d in D if d not in FOMC])
for nom,g in R.groupby('objetivo'):
    v=g.pnl; m=v.mean(); t=m/v.std()*np.sqrt(len(v)); mitad=g.fecha.iloc[len(g)//2]
    print(f"Trampa BPR sobre el rango de 30 min · objetivo {nom}: {len(g)} trades en {n_dias} días ({len(g)/n_dias*252:.0f}/año) · ${m:.1f}/trade · t {t:.2f} · gana {np.mean(v>0):.0%} · mitades ${g[g.fecha<mitad].pnl.mean():.1f}/${g[g.fecha>=mitad].pnl.mean():.1f} · total 8 años ${v.sum():,.0f} con 1 MNQ")
R.to_pickle('bpr.pkl')
