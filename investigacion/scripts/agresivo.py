exec(open('bt2.py').read().split("print('RANGO 30 MIN")[0])
import numpy as np
# versiones que devuelven las operaciones completas (lado, entrada, salida, vela entrada, vela salida)
def orb_t(g):
    o,h,l,c = g.o,g.h,g.l,g.c; hi, lo = h[:6].max(), l[:6].min()
    for i in range(6, CIERRE+1):
        up, dn = h[i] > hi, l[i] < lo
        if up and dn: return []
        if up or dn:
            s = 1 if up else -1; st = lo if up else hi; e = max(hi, o[i]) if up else min(lo, o[i])
            if (s==1 and c[i] <= st) or (s==-1 and c[i] >= st): return [(s,e,st,i,i)]
            maxp = max(0,(c[i]-e)*s*USD)
            for j in range(i+1, CIERRE+1):
                x, maxp = gestiona(s, e, j, g, st, None, dict(tipo='be', activa=150), maxp)
                if x is not None: return [(s,e,x,i,j)]
            return [(s,e,c[CIERRE],i,CIERRE)]
    return []
def ruido_t(g, hist, prev):
    o,h,l,c,v = g.o,g.h,g.l,g.c,g.v; op=o[0]
    sig = np.array([np.mean([m[i] if len(m)>i else m[-1] for m in hist]) for i in range(len(c))])
    ub = max(op,prev)*(1+sig); lb = min(op,prev)*(1-sig)
    vw = np.cumsum((h+l+c)/3*v)/np.maximum(np.cumsum(v),1)
    pos=0; e=0; ie=0; res=[]; maxp=0; regla=dict(tipo='escalera', activa=200)
    for i in range(CIERRE):
        if pos and i > ie:
            x, maxp = gestiona(pos, e, i, g, None, None, regla, maxp)
            if x is not None: res.append((pos,e,x,ie,i)); pos=0
        fin=(i+1)*5+570
        if fin < 600 or fin % 30: continue
        old=pos
        if pos==1 and c[i] < max(ub[i],vw[i]): res.append((1,e,c[i],ie,i)); pos=0
        elif pos==-1 and c[i] > min(lb[i],vw[i]): res.append((-1,e,c[i],ie,i)); pos=0
        if pos==0:
            s = 1 if c[i]>ub[i] else -1 if c[i]<lb[i] else 0
            if s and old==s: t=res.pop(); pos,e,ie=s,t[1],t[3]
            elif s: pos,e,ie,maxp=s,c[i],i,0
    if pos: res.append((pos,e,c[CIERRE],ie,CIERRE))
    return res
def dia(trs, g):
    """(resultado del día, peor momento del día) en US$ con 1 MNQ por operación, costos incluidos."""
    peor=0.0
    for t in range(78):
        v=0.0
        for s,e,x,a,b in trs:
            if t > b: v += s*(x-e)*USD - COSTO
            elif t >= a: v += s*(((g.l[t] if s==1 else g.h[t]) - e))*USD - COSTO
        peor=min(peor,v)
    return sum(s*(x-e)*USD-COSTO for s,e,x,a,b in trs), peor
D_orb=[]; D_ru=[]
for k in range(14,len(arr)):
    g=arr[k]; hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    D_orb.append(dia(orb_t(g),g)); D_ru.append(dia(ruido_t(g,hist,arr[k-1].c[-1]),g))
D_orb=np.array(D_orb); D_ru=np.array(D_ru)
print(f'1 MNQ: ORB ${D_orb[:,0].mean():.1f}/día · Ruido ${D_ru[:,0].mean():.1f}/día · peor momento de un día (ambas) ${ (D_orb[:,1]+D_ru[:,1]).min():,.0f}')

def examen(no, nr, n=20000, dias=60, seed=2):
    rng=np.random.default_rng(seed); pasa=[]; d_pasa=[]
    for _ in range(n):
        bal=0.0; alto=0.0; mll=-2000.0; bloq=False; mejor=0.0; ok=False
        for d in range(dias):
            k=rng.integers(len(D_orb))
            r = no*D_orb[k,0] + nr*D_ru[k,0]; peor = no*D_orb[k,1] + nr*D_ru[k,1]
            if bal + peor <= mll: break                      # se quema durante el día
            bal += r; mejor=max(mejor,r)
            if bal <= mll: break
            if not bloq:
                alto=max(alto,bal); mll=alto-2000
                if bal>2100: mll=100; bloq=True
            if bal>=3000 and mejor<=0.5*bal: ok=True; d_pasa.append(d+1); break
        pasa.append(ok)
    p=np.mean(pasa)
    return p, (np.median(d_pasa) if d_pasa else None)
print('\nExamen Lucid Flex 50K (meta $3,000, pérdida máx. $2,000), máximo 60 días por intento:')
print('MNQ ORB / Ruido | pasa | días para pasar (mediana) | exámenes por cuenta aprobada | costo de exámenes por cuenta ($90 c/u)')
for no,nr in [(1,1),(2,2),(3,3),(4,4),(5,5),(6,0),(0,6),(8,8)]:
    p,dmed = examen(no,nr)
    print(f'      {no} / {nr}       | {p:5.0%} | {dmed} | {1/p:4.1f} | ${90/p:,.0f}')

def anio(ne, nf, precio=90, mensual=23, dias=252, n=10000, seed=3):
    """Examen con ne MNQ por estrategia; ya fondeada con nf MNQ. 12 meses. Recompra al quemar."""
    rng=np.random.default_rng(seed); netos=[]; d_fondeo=[]; exs=[]
    for _ in range(n):
        gasto=precio; neto=0.0; fase='ex'; bal=0.0; alto=0.0; mll=-2000.0; bloq=False; mejor=0.0
        cd=0; cp=0.0; npag=0; ex=1; df=None
        for d in range(dias):
            k=rng.integers(len(D_orb)); m = ne if fase=='ex' else nf
            r = m*(D_orb[k,0]+D_ru[k,0]); peor = m*(D_orb[k,1]+D_ru[k,1])
            if bal+peor <= mll or bal+r <= mll:
                gasto+=precio; ex+=1; fase='ex'; bal=0.0; alto=0.0; mll=-2000.0; bloq=False; mejor=0.0; continue
            bal+=r
            if fase=='ex': mejor=max(mejor,r)
            else: cp+=r; cd += r>=150
            if not bloq:
                alto=max(alto,bal); mll=alto-2000
                if bal>2100: mll=100; bloq=True
            if fase=='ex':
                if bal>=3000 and mejor<=0.5*bal:
                    fase='f'; bal=0.0; alto=0.0; mll=-2000.0; bloq=False; cd=0; cp=0.0
                    if df is None: df=d+1
            elif cd>=5 and cp>0 and npag<5:
                ret=min(0.5*bal,2000)
                if ret>=500: neto+=0.9*ret; bal-=ret; npag+=1; mll=100; bloq=True; cd=0; cp=0.0
        netos.append(neto-gasto-mensual*12); d_fondeo.append(df if df else 999); exs.append(ex)
    netos=np.array(netos); dfo=np.array(d_fondeo)
    return netos.mean(), np.median(netos), np.mean(netos<0), np.median(dfo), np.mean(dfo<=21), np.mean(exs)
print('\n12 meses (examen $90, CrossTrade $23/mes):')
print('examen MNQ c/u → fondeada MNQ c/u | neto medio | mediana | pierde | días hábiles hasta fondearse (mediana) | fondeado en el 1er mes | exámenes')
for ne,nf in [(1,1),(2,1),(3,1),(5,1),(2,2),(3,2),(5,2)]:
    a,b,c,d,e,f = anio(ne,nf)
    print(f'        {ne} → {nf}                  | ${a:>6,.0f} | ${b:>6,.0f} | {c:4.0%} | {d:>5.0f} | {e:4.0%} | {f:4.1f}')
