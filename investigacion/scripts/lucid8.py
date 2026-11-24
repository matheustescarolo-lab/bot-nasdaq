import os, numpy as np
exec(open('validar8.py').read().split("print(f\"{'':<40}")[0])
def examen(pnl, n=20000, dias=60, seed=4):
    rng=np.random.default_rng(seed); ok=[]; dd=[]
    for _ in range(n):
        bal=0; alto=0; mll=-2000; bloq=False; mejor=0; p=False
        for d in range(dias):
            x=pnl[rng.integers(len(pnl))]; bal+=x; mejor=max(mejor,x)
            if bal<=mll: break
            if not bloq:
                alto=max(alto,bal); mll=alto-2000
                if bal>2100: mll=100; bloq=True
            if bal>=3000 and mejor<=0.5*bal: p=True; dd.append(d+1); break
        ok.append(p)
    return np.mean(ok), np.median(dd) if dd else None
A=S['Combinado actual (BE + escalera)'].values; B=S['Combinado con filtro tendencia'].values
for m in (1,2,3):
    pa,da=examen(m*A); pb,db=examen(m*B)
    print(f'{m} MNQ c/u · actual: pasa {pa:.0%} en ~{da} días · con filtro tendencia: pasa {pb:.0%} en ~{db} días')
