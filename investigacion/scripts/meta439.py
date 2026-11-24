import numpy as np
exec(open("profit.py").read().split("starts=list")[0])
starts=list(range(0,len(fechas)-260,3)); FEE=439*EUR
for nom,mit in (('pruebas',False),('mitad',True)):
    E=escenario('real','todo',mit)
    for base in (6,12):
        for n in (1,2,3,4,5,6,8):
            R=np.array([plan(s,E,n,base) for s in starts])
            g=R[:,0]-(R[:,1]-R[:,2])*FEE; gasto=R[:,1]*439; perdido=(R[:,1]-R[:,2])*439
            print(f"{nom} {base} {n}: ninguna {np.mean(R[:,2]==0):.0%} · gana {np.mean(g>0):.0%} · mediana ${np.median(g):,.0f} · prom ${g.mean():,.0f} · p10 ${np.percentile(g,10):,.0f} · p90 ${np.percentile(g,90):,.0f} · gasto medio €{gasto.mean():,.0f} · retos quemados medio €{perdido.mean():,.0f}",flush=True)
