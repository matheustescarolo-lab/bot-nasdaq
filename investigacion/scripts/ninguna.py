import numpy as np
exec(open("asegurar_lib.py").read())
for nom,mit in (('COMPLETA',False),('MITAD',True)):
    E=escenario('real','todo',mit)
    for base in (6,12):
        R=np.array([hasta_pasar(s,E,base,1,5,252) for s in range(0,len(fechas)-260,3)])
        print(nom,base,' '.join(f"{n}:{np.mean(R[:,0]>n):.0%}" for n in (1,2,3,4,5,6,8,10)), 'ninguna en 12m aun sin límite:',f"{np.mean(R[:,0]==99):.0%}")
