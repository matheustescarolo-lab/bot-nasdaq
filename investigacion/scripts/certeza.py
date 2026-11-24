import numpy as np
exec(open("asegurar_lib.py").read())
Eb=escenario('real','todo',False)
Co,Wo,Cr,Wr,mo,mr=Eb; t=np.arange(1,79)/78
def sin(f):  # quitar fracción f de la ventaja media de cada estrategia
    mco=np.nanmean(Co[:,-1]); mcr=np.nanmean(Cr[:,-1])
    return (Co-f*mco*t,Wo-f*mco*t,Cr-f*mcr*t,Wr-f*mcr*t,mo,mr)
print('ventaja media $/día por MNQ: orb',np.nanmean(Co[:,-1]).round(1),'ruido',np.nanmean(Cr[:,-1]).round(1))
starts=list(range(0,len(fechas)-260,3))
for nom,E in (('pruebas',Eb),('mitad',sin(0.5)),('cuarto',sin(0.75)),('sin ventaja',sin(1.0))):
    for base in (6,12):
        R=np.array([hasta_pasar(s,E,base,1,5,252) for s in starts])
        line=f"{nom:12} {base:2}: ninguna con 4: {np.mean(R[:,0]>4):.0%} · con 10: {np.mean(R[:,0]>10):.0%}"
        if nom=='pruebas':
            yrs=fechas[starts].year; line+=' | por año (4 retos): '+' '.join(f"{y}:{np.mean(R[yrs==y,0]>4):.0%}" for y in sorted(set(yrs)))
        print(line)
