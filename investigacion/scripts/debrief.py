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
starts=list(range(0,len(fechas)-260,3)); FEE=439*EUR
for nom,mit in (('pruebas',False),('mitad',True)):
    Co,Wo,Cr,Wr,mo,mr=escenario('ambos_sac','todo',mit); E=(Co,Wo,Cr,Wr,np.minimum(mo,2.0),np.minimum(mr,2.0))
    R=[plan2(s,E,4,6) for s in starts]; A=np.array([r[:3] for r in R]); t1=np.array([r[3] for r in R if r[3] is not None])
    gasto=A[:,1]*439; perdida=(A[:,1]-A[:,2])*439; g=A[:,0]-(A[:,1]-A[:,2])*FEE
    p=lambda v,q: np.percentile(v,q)
    print(f"{nom}: retos comprados p10/med/p90 {p(A[:,1],10):.0f}/{np.median(A[:,1]):.0f}/{p(A[:,1],90):.0f} · gasto € {p(gasto,10):.0f}/{np.median(gasto):.0f}/{p(gasto,90):.0f} (máx {gasto.max():.0f}) · perdido € {p(perdida,10):.0f}/{np.median(perdida):.0f}/{p(perdida,90):.0f}")
    print(f"   profit 12m p10 ${p(g,10):,.0f} · p25 ${p(g,25):,.0f} · mediana ${np.median(g):,.0f} · promedio ${g.mean():,.0f} · p75 ${p(g,75):,.0f} · p90 ${p(g,90):,.0f} · gana {np.mean(g>0):.0%} · no cobra {np.mean(A[:,2]==0):.0%}")
    print(f"   1er cobro (días hábiles desde la compra) p10/med/p90: {p(t1,10):.0f}/{np.median(t1):.0f}/{p(t1,90):.0f} · cobra en 12 m {len(t1)/len(R):.0%}")
