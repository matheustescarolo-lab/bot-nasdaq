import numpy as np
exec(open('escalera.py').read().split("for nom,mit")[0])
def plan(s,E,size,nmax,bc,H=252,reinv=False):
    ctas=[]; compras=0; gasto=0.0; caja=0.0; tpaso=None
    for i,k in enumerate(range(s,min(s+H,len(fechas)))):
        act=[c for c in ctas if c.est in('p1','p2')]; fond=[c for c in ctas if c.est=='f']
        if not act and not fond and compras<nmax: c=Cta(size,i); ctas.append(c); gasto+=c.fee; compras+=1
        if reinv and fond and not act:
            for t in (200,100,50,25,10):
                if caja>=PRECIO[t]*EUR and sum(c.size for c in fond)+t<=400: c=Cta(t,i); ctas.append(c); caja-=c.fee; break
        for c in ctas:
            if c.est=='x': continue
            if c.est in('p1','p2'):
                mf=(0.10 if c.est=='p1' else 0.05)*1e5; r,peor=(0.0,0.0) if c.listo else corre(k,bc,E,max(mf-c.bal,100))
            else: r,peor=corre(k,4,E,None)
            if c.bal+peor<=max(c.prev-5000,-10000): c.est='x'; continue
            c.bal+=r; c.prev=c.bal; c.dias+=1
            if c.est in('p1','p2'):
                if c.bal>=mf: c.listo=True
                if c.listo and c.dias>=4:
                    if c.est=='p2' and tpaso is None: tpaso=i
                    c.est='p2' if c.est=='p1' else 'f'; c.bal=c.prev=0.0; c.dias=0; c.listo=False
            else:
                c.df+=1
                if c.df%10==0 and c.bal>0:
                    caja+=0.8*c.bal*c.f+(c.fee if c.reemb else 0); c.reemb=False; c.bal=c.prev=0.0
    return caja-gasto, tpaso
PL=[('10K',10,5,6,False),('10K→sube',10,5,6,True),('100K',100,5,6,False),('100K x3 agresivo',100,3,12,False)]
for nom,mit in (('COMPLETA',False),('MITAD',True)):
    E=escenario('real','todo',mit); print(nom)
    for H in (126,252):
        for n,size,nm,bc,rv in PL:
            R=[plan(s,E,size,nm,bc,H,rv) for s in range(0,len(fechas)-H-5,3)]
            g=np.array([r[0] for r in R]); t=[r[1] for r in R if r[1] is not None]
            print(f" {H//21:2}m {n:18} €{PRECIO[size]*nm:5} pasa {len(t)/len(R):4.0%} en {np.median(t) if t else 0:4.0f}d | gana {np.mean(g>0):4.0%} mediana ${np.median(g):8,.0f} prom ${g.mean():8,.0f} p25 ${np.percentile(g,25):8,.0f} p75 ${np.percentile(g,75):8,.0f}")
