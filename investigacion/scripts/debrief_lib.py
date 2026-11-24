import numpy as np, builtins, io
_open=builtins.open
def abrir(p,*a,**k):
    f=_open(p,*a,**k)
    if p in('final2.py','escalera.py','asegurar_lib.py','profit.py'):
        t=f.read().replace("final_caminos.npz","final_caminos2.npz"); f.close(); return io.StringIO(t)
    return f
builtins.open=abrir
exec(open('profit.py').read().split("starts=list")[0])
builtins.open=_open
def plan2(s,E,nmax,bc,H=252):
    ctas=[]; compras=0; pago=0.0; reemb=0; t1=None
    for i,k in enumerate(range(s,min(s+H,len(fechas)))):
        if not any(c.est in('p1','p2','f') for c in ctas) and compras<nmax: ctas.append(Cta(100,i)); compras+=1
        for c in ctas:
            if c.est=='x': continue
            if c.est in('p1','p2'):
                mf=(0.10 if c.est=='p1' else 0.05)*1e5; r,peor=(0.0,0.0) if c.listo else corre(k,bc,E,max(mf-c.bal,100))
            else: r,peor=corre(k,4,E,None)
            if c.bal+peor<=max(c.prev-5000,-10000): c.est='x'; continue
            c.bal+=r; c.prev=c.bal; c.dias+=1
            if c.est in('p1','p2'):
                if c.bal>=mf: c.listo=True
                if c.listo and c.dias>=4: c.est='p2' if c.est=='p1' else 'f'; c.bal=c.prev=0.0; c.dias=0; c.listo=False
            else:
                c.df+=1
                if c.df%10==0 and c.bal>0:
                    pago+=0.8*c.bal; reemb+= 1 if c.reemb else 0; c.reemb=False; c.bal=c.prev=0.0
                    if t1 is None: t1=i
    return pago,compras,reemb,t1
