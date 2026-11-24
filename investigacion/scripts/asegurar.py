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
for nom,mit in (('VENTAJA COMPLETA',False),('MEDIA VENTAJA',True)):
    E=escenario('real','todo',mit); print('\n',nom)
    for base in (12,8,6):
        for conc in (2,1):
            R=np.array([hasta_pasar(s,E,base,conc) for s in range(0,len(fechas)-520,3)])
            n=R[:,0]; d=R[:,1]
            q=lambda p:np.percentile(n,p,method='higher')
            print(f"base {base:2} conc {conc}: retos para 80% {q(80)} · 90% {q(90)} · 95% {q(95)} · 99% {q(99)} | prob con 3/5/8/10: {np.mean(n<=3):.0%}/{np.mean(n<=5):.0%}/{np.mean(n<=8):.0%}/{np.mean(n<=10):.0%} | días hábiles mediana {np.median(d):.0f} p90 {np.percentile(d,90):.0f} | nunca {np.mean(n==99):.1%}")
