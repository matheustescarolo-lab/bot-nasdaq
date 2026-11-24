import numpy as np
exec(open("profit.py").read().split("starts=list")[0])
starts=list(range(0,len(fechas)-260,3)); FEE=439*EUR
for nom,mit in (('pruebas',False),('mitad',True)):
    E0=escenario('real','todo',mit)
    for tope in (None,2.0,1.5):
        Co,Wo,Cr,Wr,mo,mr=E0
        if tope: mo=np.minimum(mo,tope); mr=np.minimum(mr,tope)
        E=(Co,Wo,Cr,Wr,mo,mr); base=6
        no=np.round(base*mo); nr=np.round(base*mr); wt=-np.nanmin(no[:,None]*Wo+nr[:,None]*Wr,axis=1)/1e3
        R=np.array([plan(s,E,4,base) for s in starts]); g=R[:,0]-(R[:,1]-R[:,2])*FEE
        print(f"{nom:8} tope {tope}: máx MNQ {max(no.max(),nr.max()):.0f} · riesgo día p90 {np.percentile(wt[wt>0],90):.1f}% p99 {np.percentile(wt[wt>0],99):.1f}% | no cobra {np.mean(R[:,2]==0):.0%} · gana {np.mean(g>0):.0%} · mediana ${np.median(g):,.0f} · prom ${g.mean():,.0f}",flush=True)
