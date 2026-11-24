import numpy as np
exec(open("asegurar_lib.py").read())
for nom,mit in (('COMPLETA',False),('MITAD',True)):
    E=escenario('real','todo',mit)
    for base in (6,12):
        R=np.array([hasta_pasar(s,E,base,1,5,252) for s in range(0,len(fechas)-260,3)])
        out=[]
        for n in (1,2,3,4,5,6,8,10):
            d=R[R[:,0]<=n,1]; out.append(f"{n}:{np.median(d)/21:.1f}m/p90 {np.percentile(d,90)/21:.1f}m")
        print(nom,base,' | '.join(out))
