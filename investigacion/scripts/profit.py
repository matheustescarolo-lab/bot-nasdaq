import numpy as np
exec(open("asegurar_lib.py").read())
P={10:89,25:250,50:345,100:540,200:1080}
def plan(s,E,nmax,bc,H=252):
    ctas=[]; compras=0; pago=0.0; reemb=0
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
    return pago,compras,reemb
starts=list(range(0,len(fechas)-260,3))
for nom,mit in (('pruebas',False),('mitad',True)):
    E=escenario('real','todo',mit)
    for base in (6,12):
        for n in (1,2,3,4,5,6,8,10):
            R=np.array([plan(s,E,n,base) for s in starts])
            out=[]
            for sz,fee in P.items():
                g=R[:,0]*sz/100-(R[:,1]-R[:,2])*fee*EUR
                out.append(f"{sz}K med {np.median(g):,.0f} prom {g.mean():,.0f}")
            print(nom,base,n,' | '.join(out),flush=True)
