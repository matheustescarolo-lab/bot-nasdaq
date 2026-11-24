exec(open("debrief_lib.py").read())
FEE=439*EUR
def sim(s,Es,modo,H=504):
    E,Eo,Er=Es; ctas=[]; propias=0; caja=0.0; bolsillo=0.0; hist=[]; n_f=0
    for i,k in enumerate(range(s,min(s+H,len(fechas)))):
        enreto=any(c.est in('p1','p2') for c in ctas); fond=sum(c.est=='f' for c in ctas)
        if not enreto and fond<4:
            if caja>=FEE and fond>=1: ctas.append(Cta(100,i)); caja-=FEE
            elif fond==0 and propias<4: ctas.append(Cta(100,i)); propias+=1; bolsillo+=FEE
        for c in ctas:
            if c.est=='x': continue
            if c.est in('p1','p2'):
                mf=(0.10 if c.est=='p1' else 0.05)*1e5; r,peor=(0.0,0.0) if c.listo else corre(k,6,E,max(mf-c.bal,100))
            else:
                if not hasattr(c,'id'): c.id=n_f; n_f+=1
                if modo=='igual': r,peor=corre(k,4,E,None)
                elif modo=='dividir4': r,peor=corre(k,4,(Eo if c.id%2==0 else Er),None)
                elif modo=='dividir6': r,peor=corre(k,6,(Eo if c.id%2==0 else Er),None)
                elif modo=='tamaños': r,peor=corre(k,[3,4,5][c.id%3],E,None)
                elif modo=='colchón':
                    colchon=c.bal+10000; b=max(1,round(4*min(1.5,max(0.5,colchon/10000))))
                    r,peor=corre(k,b,E,None)
            if c.bal+peor<=max(c.prev-5000,-10000): c.est='x'; continue
            c.bal+=r; c.prev=c.bal; c.dias+=1
            if c.est in('p1','p2'):
                if c.bal>=mf: c.listo=True
                if c.listo and c.dias>=4: c.est='p2' if c.est=='p1' else 'f'; c.bal=c.prev=0.0; c.dias=0; c.listo=False
            else:
                c.df+=1
                if c.df%10==0 and c.bal>0:
                    caja+=0.8*c.bal+(FEE if c.reemb else 0); c.reemb=False; c.bal=c.prev=0.0
        if i%21==20: hist.append((sum(c.est=='f' for c in ctas), caja-bolsillo, sum(c.est=='x' and hasattr(c,'id') for c in ctas)))
    return hist
starts=list(range(0,len(fechas)-510,3))
for nom,mit in (('mitad',True),):
    Co,Wo,Cr,Wr,mo,mr=escenario('ambos_sac','todo',mit); mo=np.minimum(mo,2.0); mr=np.minimum(mr,2.0)
    E=(Co,Wo,Cr,Wr,mo,mr); Z0=np.zeros_like(Co); Eo=(Co,Wo,Z0,Z0,mo,mr); Er=(Z0,Z0,Cr,Wr,mo,mr)
    for modo in ('igual','dividir4','dividir6','tamaños','colchón'):
        R=[sim(s,(E,Eo,Er),modo) for s in starts]; Hh=np.array([r for r in R if len(r)>=24])
        f=Hh[:,:,0]; g=Hh[:,:,1]; q=Hh[:,:,2]
        print(f"{nom:8} {modo:9} | 12 m mediana ${np.median(g[:,11]):,.0f} · 24 m mediana ${np.median(g[:,23]):,.0f} (p10 ${np.percentile(g[:,23],10):,.0f}) · fondeadas quemadas en 24 m {q[:,23].mean():.1f} · sin cuenta viva al mes 24 {np.mean(f[:,23]==0):.0%} · pierde {np.mean(g[:,23]<0):.0%}",flush=True)
