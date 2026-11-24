exec(open("debrief_lib.py").read())
starts=list(range(0,len(fechas)-260,3))
for nom,mit in (('pruebas',False),('mitad',True)):
    Co,Wo,Cr,Wr,mo,mr=escenario('ambos_sac','todo',mit); E=(Co,Wo,Cr,Wr,np.minimum(mo,2.0),np.minimum(mr,2.0))
    R=[plan2(s,E,4,6) for s in starts]; A=np.array([r[:3] for r in R])
    for tam,fee in ((100,439),(100,540),(50,345),(50,279)):
        f=tam/100; g=A[:,0]*f-(A[:,1]-A[:,2])*fee*EUR; p=lambda v,q: np.percentile(v,q)
        print(f"{nom:8} {tam}K €{fee}: reserva €{4*fee:,} · perdido típico €{np.median((A[:,1]-A[:,2])*fee):.0f} · profit p10 ${p(g,10):,.0f} · mediana ${np.median(g):,.0f} · p90 ${p(g,90):,.0f} · gana {np.mean(g>0):.0%}")
