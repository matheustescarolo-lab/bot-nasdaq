import numpy as np
src=open('profit.py').read().split("starts=list")[0]
# profit.py → asegurar_lib → escalera → final2: cambiar el archivo de caminos
import builtins
_open=builtins.open
def abrir(p,*a,**k):
    f=_open(p,*a,**k)
    if p in('final2.py','escalera.py','asegurar_lib.py','profit.py'):
        t=f.read().replace("final_caminos.npz","final_caminos2.npz"); f.close()
        import io; return io.StringIO(t)
    return f
builtins.open=abrir
exec(src)
builtins.open=_open
starts=list(range(0,len(fechas)-260,3)); FEE=439*EUR
for costos in ('real','ambos_sac'):
  for nom,mit in (('pruebas',False),('mitad',True)):
    Co,Wo,Cr,Wr,mo,mr=escenario(costos,'todo',mit); mo=np.minimum(mo,2.0); mr=np.minimum(mr,2.0); E=(Co,Wo,Cr,Wr,mo,mr)
    z=mo*Co[:,-1]+mr*Cr[:,-1]
    for n in (1,2,3,4,6):
        R=np.array([plan(s,E,n,6) for s in starts]); g=R[:,0]-(R[:,1]-R[:,2])*FEE
        print(f"{costos:9} {nom:7} $/día {z.mean():.1f} | {n} retos: no cobra {np.mean(R[:,2]==0):.0%} · gana {np.mean(g>0):.0%} · mediana ${np.median(g):,.0f} · prom ${g.mean():,.0f}",flush=True)
