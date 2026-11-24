import numpy as np
exec(open('productos.py').read().split("import sys")[0])
def hacer(col):
    def d(k,base,C,meta,room):
        Co,Wo,Cr,Wr=C; no=round(base*MO[k]); nr=round(base*MR[k]); m=no+nr
        if m==0: return 0.0,False
        c=no*Co[k]+nr*Cr[k]; w=no*Wo[k]+nr*Wr[k]
        fr=room-(col(m) if col else 0)
        q=np.flatnonzero(w<=-room); f=np.flatnonzero(w<=-fr) if col else np.array([],int); g=np.flatnonzero(c>=meta) if meta is not None else np.array([],int)
        t=min([x[0] for x in (q,f,g) if len(x)]+[99])
        if t==99: return c[-1],False
        if len(q) and q[0]==t: return -room,True
        if len(f) and f[0]==t: return -fr-4.0*m,False
        return c[t],False
    return d
for mit,nom in ((False,'pruebas'),(True,'mitad')):
    C=caminos(mit)
    for etq,col in (('sin freno',None),('colchón $100',lambda m:100),('colchón $400',lambda m:400),('actual max($400,30pts)',lambda m:max(400,60*m))):
        globals()['dia']=hacer(col); print(f"{nom:7} {etq:24}", res(lambda s: dos_pasos(s,C,4)),flush=True)
