exec(open("debrief_lib.py").read())
def plan3(s,E,nmax,t1,t2,mind,H=252):
    ctas=[]; compras=0; pago=0.0; reemb=0
    for i,k in enumerate(range(s,min(s+H,len(fechas)))):
        if not any(c.est in('p1','p2','f') for c in ctas) and compras<nmax: ctas.append(Cta(100,i)); compras+=1
        for c in ctas:
            if c.est=='x': continue
            if c.est in('p1','p2'):
                mf=(t1 if c.est=='p1' else t2)*1e5; r,peor=(0.0,0.0) if c.listo else corre(k,6,E,max(mf-c.bal,100))
            else: r,peor=corre(k,4,E,None)
            if c.bal+peor<=max(c.prev-5000,-10000): c.est='x'; continue
            c.bal+=r; c.prev=c.bal; c.dias+=1
            if c.est in('p1','p2'):
                if c.bal>=mf: c.listo=True
                if c.listo and c.dias>=mind: c.est='p2' if c.est=='p1' else 'f'; c.bal=c.prev=0.0; c.dias=0; c.listo=False
            else:
                c.df+=1
                if c.df%10==0 and c.bal>0: pago+=0.8*c.bal; reemb+= 1 if c.reemb else 0; c.reemb=False; c.bal=c.prev=0.0
    return pago,compras,reemb
starts=list(range(0,len(fechas)-260,3))
FIRMAS=[('FTMO 100K',100,483,0.10,0.05,4),('FTMO 50K',50,380,0.10,0.05,4),('FundedNext 100K',100,530,0.08,0.05,5),('FundedNext 50K',50,300,0.08,0.05,5),('FundedNext 25K',25,200,0.08,0.05,5),("The5ers 100K",100,442,0.10,0.05,3)]
for nom,mit in (('pruebas',False),('mitad',True)):
    Co,Wo,Cr,Wr,mo,mr=escenario('ambos_sac','todo',mit); E=(Co,Wo,Cr,Wr,np.minimum(mo,2.0),np.minimum(mr,2.0))
    cache={}
    for f,tam,fee,t1,t2,md in FIRMAS:
        for n in (1,2,3):
            key=(t1,t2,md,n)
            if key not in cache: cache[key]=np.array([plan3(s,E,n,t1,t2,md) for s in starts])
            A=cache[key]; g=A[:,0]*tam/100-(A[:,1]-A[:,2])*fee
            print(f"{nom:8} {f:16} {n} retos (reserva ${n*fee:,}) · no cobra {np.mean(A[:,2]==0):.0%} · mediana ${np.median(g):,.0f} · gana {np.mean(g>0):.0%}",flush=True)
