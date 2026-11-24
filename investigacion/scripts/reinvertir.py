exec(open("debrief_lib.py").read())
FEE=439*EUR
def sim(s,E,reinv,H=504,max_bolsillo=4,tope_fond=4):
    ctas=[]; propias=0; caja=0.0; bolsillo=0.0; hist=[]
    for i,k in enumerate(range(s,min(s+H,len(fechas)))):
        enreto=any(c.est in('p1','p2') for c in ctas); fond=sum(c.est=='f' for c in ctas)
        if not enreto and fond<tope_fond:
            if reinv and caja>=FEE and fond>=1: ctas.append(Cta(100,i)); caja-=FEE            # con ganancias
            elif fond==0 and propias<max_bolsillo: ctas.append(Cta(100,i)); propias+=1; bolsillo+=FEE   # de tu bolsillo
        for c in ctas:
            if c.est=='x': continue
            if c.est in('p1','p2'):
                mf=(0.10 if c.est=='p1' else 0.05)*1e5; r,peor=(0.0,0.0) if c.listo else corre(k,6,E,max(mf-c.bal,100))
            else: r,peor=corre(k,4,E,None)
            if c.bal+peor<=max(c.prev-5000,-10000): c.est='x'; continue
            c.bal+=r; c.prev=c.bal; c.dias+=1
            if c.est in('p1','p2'):
                if c.bal>=mf: c.listo=True
                if c.listo and c.dias>=4: c.est='p2' if c.est=='p1' else 'f'; c.bal=c.prev=0.0; c.dias=0; c.listo=False
            else:
                c.df+=1
                if c.df%10==0 and c.bal>0:
                    caja+=0.8*c.bal+(FEE if c.reemb else 0); c.reemb=False; c.bal=c.prev=0.0
        if i%21==20: hist.append((sum(c.est=='f' for c in ctas), caja-bolsillo))
    return hist, bolsillo
starts=list(range(0,len(fechas)-510,3))
for nom,mit in (('pruebas',False),('mitad',True)):
    Co,Wo,Cr,Wr,mo,mr=escenario('ambos_sac','todo',mit); E=(Co,Wo,Cr,Wr,np.minimum(mo,2.0),np.minimum(mr,2.0))
    for reinv in (False,True):
        R=[sim(s,E,reinv) for s in starts]
        H=np.array([r[0] for r in R if len(r[0])>=24])  # (inicios, meses, 2)
        f=H[:,:,0]; g=H[:,:,1]
        lin=f"{nom:8} {'reinvierte' if reinv else 'una cuenta':10} |"
        for m in (6,12,18,24):
            lin+=f" mes {m}: cuentas fondeadas prom {f[:,m-1].mean():.1f}, ganancia neta mediana ${np.median(g[:,m-1]):,.0f} (p10 ${np.percentile(g[:,m-1],10):,.0f}, p90 ${np.percentile(g[:,m-1],90):,.0f}) |"
        pierde=np.mean(g[:,23]<0); cero=np.mean(f[:,23]==0)
        t4=[np.argmax(x>=4)+1 if (x>=4).any() else None for x in f]; t4v=[t for t in t4 if t]
        lin+=f" a 24 m: pierde dinero {pierde:.0%}, sin cuenta viva {cero:.0%}" + (f", llega a 4 cuentas {len(t4v)/len(t4):.0%} (mediana mes {np.median(t4v):.0f})" if reinv and t4v else '')
        print(lin, flush=True)
