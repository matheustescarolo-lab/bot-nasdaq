import numpy as np
exec(open('final2.py').read().split("for nom,costos")[0])
EUR=1.10; PRECIO={10:89,25:250,50:345,100:540,200:1080}; TIERS=[10,25,50,100,200]
class Cta:
    def __init__(s,size,dia): s.size=size; s.f=size/100; s.fee=PRECIO[size]*EUR; s.est='p1'; s.bal=s.prev=0.0; s.dias=0; s.listo=False; s.reemb=True; s.df=0; s.ini=dia
def sim(s,E,size0,n_compra,conc,reinv,H=126):
    caja=0.0; gasto=0.0; cobrado=0.0; ctas=[]; compras=0; pasos=0
    for i,k in enumerate(range(s,min(s+H,len(fechas)))):
        vivas=[c for c in ctas if c.est!='x']
        # comprar con presupuesto inicial (escalonado: 1 nuevo cada 5 días como máx)
        if compras<n_compra and sum(c.est in('p1','p2') for c in vivas)<conc and not any(c.ini>i-5 for c in vivas if c.est in('p1','p2')):
            c=Cta(size0,i); ctas.append(c); gasto+=c.fee; compras+=1
        # reinvertir ganancias
        if reinv:
            fondeado=sum(c.size for c in vivas if c.est=='f')
            enreto=sum(c.est in('p1','p2') for c in vivas)
            for t in reversed(TIERS):
                if caja>=PRECIO[t]*EUR and fondeado+t<=400 and enreto<3:
                    c=Cta(t,i); ctas.append(c); caja-=c.fee; gasto+=0; enreto+=1; break
        for c in ctas:
            if c.est=='x': continue
            if c.est in('p1','p2'):
                mf=0.10 if c.est=='p1' else 0.05; mf*=1e5
                r,peor=(0.0,0.0) if c.listo else corre(k,12,E,max(mf-c.bal,100))
            else: r,peor=corre(k,4,E,None)
            if c.bal+peor<=max(c.prev-5000,-10000): c.est='x'; continue
            c.bal+=r; c.prev=c.bal; c.dias+=1
            if c.est in('p1','p2'):
                if c.bal>=mf: c.listo=True
                if c.listo and c.dias>=4:
                    if c.est=='p2': pasos+=1
                    c.est='p2' if c.est=='p1' else 'f'; c.bal=c.prev=0.0; c.dias=0; c.listo=False
            else:
                c.df+=1
                if c.df%10==0 and c.bal>0:
                    p=0.8*c.bal*c.f+(c.fee if c.reemb else 0); c.reemb=False; c.bal=c.prev=0.0
                    cobrado+=p; caja+=p
    # valor final = efectivo en caja (lo reinvertido ya está gastado)  -> ganancia neta en bolsillo
    return caja-gasto, pasos>0, gasto
for nom,mit in (('VENTAJA COMPLETA',False),('MEDIA VENTAJA (prudente)',True)):
    E=escenario('real','todo',mit); print('\n',nom)
    for size0,n,conc in ((10,1,1),(10,3,2),(10,5,2),(25,3,2),(50,3,2),(100,1,1),(100,2,2),(100,3,2)):
        for reinv in (False,True):
            R=[sim(s,E,size0,n,conc,reinv) for s in range(0,len(fechas)-130,3)]
            g=np.array([r[0] for r in R]); ps=np.mean([r[1] for r in R])
            print(f"{size0:>3}K x{n} €{PRECIO[size0]*n:>5} reinv={reinv!s:5} | pasa≥1 {ps:4.0%} | gana {np.mean(g>0):4.0%} | mediana ${np.median(g):>8,.0f} | prom ${g.mean():>8,.0f} | p10 ${np.percentile(g,10):>8,.0f} | p90 ${np.percentile(g,90):>8,.0f}")
