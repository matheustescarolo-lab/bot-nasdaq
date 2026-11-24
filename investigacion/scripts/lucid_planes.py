import numpy as np, sys
exec(open('productos.py').read().split("# ---------- productos")[0])
FRENO=False
def dia(k,base,C,meta,room,dll,trail=None):
    """room = distancia al piso (quema); dll = límite diario blando de Lucid; trail=(bal,piso,mll,lock) si el piso sube intradía"""
    Co,Wo,Cr,Wr=C; no=round(base*MO[k]); nr=round(base*MR[k]); m=no+nr
    if m==0: return 0.0,False,0.0
    c=no*Co[k]+nr*Cr[k]-2.0*m; w=no*Wo[k]+nr*Wr[k]-2.0*m      # +$2/MNQ de comisión de futuros
    col=max(150,60*m) if FRENO else 0.0
    if trail is None:
        r=np.full(78,room)
    else:
        bal,piso,mll,lock=trail; pk=np.maximum.accumulate(np.maximum(c,0))
        r=bal-np.minimum(np.maximum(piso,bal+pk-mll),lock)            # piso intradía que sube con el pico de equity
    L=np.minimum(dll,r-col) if FRENO else np.full(78,float(dll))
    q=np.flatnonzero(w<=-r); f=np.flatnonzero(w<=-L); g=np.flatnonzero(c>=meta) if meta is not None else np.array([],int)
    t=min([x[0] for x in (q,f,g) if len(x)]+[99])
    if t==99: return c[-1],False,c.max()
    if len(q) and q[0]==t: return -r[t],True,0
    if len(f) and f[0]==t: return -L[t]-4.0*m,False,0
    return c[t],False,c[:t+1].max()
P50=dict(flex=dict(px=80.5,tgt=3000,mll=2000,dll=1200,econs=.4),pro=dict(px=120.4,tgt=3000,mll=2000,dll=1200,econs=None),
         daily=dict(px=85.4,tgt=3000,mll=2000,dll=1200,econs=.4),direct=dict(px=360.5,tgt=None,mll=2000,dll=1200,econs=None))
P150=dict(flex=dict(px=226.1,tgt=9000,mll=4500,dll=2700,econs=.4),pro=dict(px=255.5,tgt=9000,mll=4500,dll=2700,econs=None),
          daily=dict(px=200.2,tgt=9000,mll=4500,dll=2700,econs=.4),direct=dict(px=585.2,tgt=None,mll=5000,dll=3000,econs=None))
def cuenta(s,C,plan,tam,base,H=252,maxc=15,cap_dia=False):
    p=(P50 if tam==50 else P150)[plan]; big=tam==150
    pago=0.0; compras=0; est=None; k=s; fin=min(s+H,len(fechas))
    while k<fin:
        if est is None:
            if compras>=maxc: break
            compras+=1; est='e' if p['tgt'] else 'f'; bal=0.0; pico=0.0; pos=[]; lock=False; npay=0; ciclo=[]; 
        piso=(100.0 if lock else max(0.0,pico)-p['mll']) if not (pico>=p['mll']+100) else 100.0
        if pico>=p['mll']+100: lock=True
        if est=='e':
            nec=max(p['tgt'],(max(pos)/p['econs']) if (p['econs'] and pos) else 0)
            meta=max(100,nec-bal)
            if p['econs']: meta=max(100,min(meta,0.39*nec))
            r,qm,_=dia(k,base,C,meta,bal-piso,p['dll'])
            k+=1
            if qm: est=None; continue
            bal+=r; pico=max(pico,bal)
            if r>0: pos.append(r)
            if bal>=p['tgt'] and (not p['econs'] or max(pos)<=p['econs']*bal):
                est='f'; bal=0.0; pico=0.0; lock=False; ciclo=[]
            continue
        # fondeada
        meta=None
        if plan=='direct' and cap_dia: meta=0.2*(3000 if not big else 9000)*0.95
        trail=(bal,piso,p['mll'],100.0) if plan=='daily' and not lock else None
        r,qm,pk=dia(k,base,C,meta,bal-piso,p['dll'],trail); k+=1
        if qm: est=None; continue
        if plan=='daily' and not lock: pico=max(pico,bal+pk)
        bal+=r; pico=max(pico,bal); ciclo.append(r)
        if pico>=p['mll']+100: lock=True
        retiro=0.0
        if plan=='flex':
            if sum(x>=(250 if big else 150) for x in ciclo)>=5 and sum(ciclo)>0 and bal>0:
                retiro=min(0.5*bal,3000 if big else 2000); lock=True
        elif plan=='pro':
            buf=4600 if big else 2100; cp=sum(ciclo)
            if len(ciclo)>=3 and cp>=(1000 if big else 500) and max(ciclo)<=0.4*cp and bal>buf:
                retiro=min(bal-buf,(3000 if npay==0 else 3500) if big else (2000 if npay==0 else 2500))
        elif plan=='daily':
            buf=4600 if big else 2100
            if sum(ciclo)>0 and bal-buf>=500: retiro=bal-buf
        elif plan=='direct':
            cp=sum(ciclo); goal=(9000 if npay==0 else 4500) if big else (3000 if npay==0 else 2500)
            if len(ciclo)>=5 and cp>=goal and max(ciclo)<=0.2*cp:
                retiro=min(cp,(3000 if npay<3 else 3500) if big else (2000 if npay<3 else 2500))
        if retiro>=500:
            pago+=0.9*retiro; bal-=retiro; npay+=1; ciclo=[]
            if plan!='daily' and npay>=5: est=None          # pasa a LucidLive: aquí se cuenta como cuenta terminada (conservador)
    return pago-compras*p['px']-279.0, pago>0, compras
starts=list(range(0,len(fechas)-260,5))
def res(f):
    A=np.array([f(s) for s in starts]); g=A[:,0]
    return f"no cobra {np.mean(A[:,1]==0):4.0%} · gana {np.mean(g>0):4.0%} · mediana ${np.median(g):>7,.0f} · prom ${g.mean():>7,.0f} · p10 ${np.percentile(g,10):>7,.0f} · p90 ${np.percentile(g,90):>7,.0f} · compras {A[:,2].mean():.1f}"
FRENO=len(sys.argv)>3; mit=sys.argv[1]=='mitad'; C=caminos(mit); tam=int(sys.argv[2])
for plan in ('flex','pro','daily','direct'):
    for base in ((1,2) if tam==50 else (2,3,4)):
        print(f"{sys.argv[1]:7} {tam}K {plan:6} base {base}", res(lambda s: cuenta(s,C,plan,tam,base,maxc=4 if plan=='direct' else 15)),flush=True)
    if plan=='direct':
        print(f"{sys.argv[1]:7} {tam}K direct tope20% base {base}", res(lambda s: cuenta(s,C,plan,tam,base,maxc=4,cap_dia=True)),flush=True)
