import numpy as np
exec(open("asegurar_lib.py").read())
E=escenario('real','todo',False); Co,Wo,Cr,Wr,mo,mr=E
for base in (6,12):
    no=np.round(base*mo); nr=np.round(base*mr)
    wo=no*np.nanmin(Wo,axis=1); wr=nr*np.nanmin(Wr,axis=1); wt=np.nanmin(no[:,None]*Wo+nr[:,None]*Wr,axis=1)
    for nom,w,n in (('ORB',wo,no),('Ruido',wr,nr),('Día',wt,None)):
        w=-w[w<0]/1e3  # % de 100K
        print(f"base {base} {nom:5}: peor momento del día (% cuenta) mediana {np.median(w):.1f}% · p90 {np.percentile(w,90):.1f}% · p99 {np.percentile(w,99):.1f}% · máx {w.max():.1f}%" + (f" | MNQ mediana {np.median(n[n>0]):.0f} máx {n.max():.0f}" if n is not None else ''))
