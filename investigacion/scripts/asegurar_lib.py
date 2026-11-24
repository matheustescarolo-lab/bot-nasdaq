import numpy as np
exec(open('escalera.py').read().split("for nom,mit")[0])
def hasta_pasar(s,E,base,conc=2,sep=5,H=500):
    ctas=[]; compras=0
    for i,k in enumerate(range(s,min(s+H,len(fechas)))):
        act=[c for c in ctas if c.est in('p1','p2')]
        if len(act)<conc and not any(c.ini>i-sep for c in act):
            c=Cta(10,i); ctas.append(c); compras+=1
        for c in ctas:
            if c.est not in('p1','p2'): continue
            mf=(0.10 if c.est=='p1' else 0.05)*1e5
            r,peor=(0.0,0.0) if c.listo else corre(k,base,E,max(mf-c.bal,100))
            if c.bal+peor<=max(c.prev-5000,-10000): c.est='x'; continue
            c.bal+=r; c.prev=c.bal; c.dias+=1
            if c.bal>=mf: c.listo=True
            if c.listo and c.dias>=4:
                if c.est=='p2': return compras,i
                c.est='p2'; c.bal=c.prev=0.0; c.dias=0; c.listo=False
    return 99,H