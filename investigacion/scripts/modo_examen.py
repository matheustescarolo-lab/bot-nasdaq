import os, numpy as np
src = open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0]
exec(src)
# Trayectoria dentro del día (1 MNQ por estrategia, costos incluidos): al cierre de cada vela y en el peor punto de cada vela
def caminos(trs, g):
    c=np.zeros(78); w=np.zeros(78)
    for t in range(78):
        vc=vw=0.0
        for s,e,x,a,b in trs:
            if t > b: r = s*(x-e)*USD - COSTO; vc += r; vw += r
            elif t >= a:
                vc += s*(g.c[t]-e)*USD - COSTO
                vw += s*((g.l[t] if s==1 else g.h[t]) - e)*USD - COSTO
        c[t]=vc; w[t]=vw
    return c, w
C=[]; W=[]
for k in range(20,len(arr)):
    g=arr[k]; hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    c1,w1=caminos(orb_t(g),g); c2,w2=caminos(ruido_t(g,hist,arr[k-1].c[-1]),g)
    C.append(c1+c2); W.append(w1+w2)
C=np.array(C); W=np.array(W); FIN=C[:,-1]
np.save('caminos_C.npy',C); np.save('caminos_W.npy',W)
print(f'{len(C)} días · 1 MNQ c/u: promedio ${FIN.mean():.1f}/día')

def dia(k, n, meta, freno):
    """Resultado de un día con n MNQ por estrategia, cerrando al tocar la meta o el freno. Devuelve (resultado, peor momento)."""
    c=n*C[k]; w=n*W[k]; peor=0.0
    for t in range(78):
        if freno and w[t] <= -freno: return -freno - n*1.0, min(peor, -freno)      # sale en el freno (+1 punto de deslizamiento)
        peor=min(peor,w[t])
        if meta and c[t] >= meta: return c[t], peor
    return c[-1], peor

def examen(n, meta, freno, intentos=6000, max_dias=40, seed=5):
    rng=np.random.default_rng(seed); pasa=0; dias_tot=0
    for _ in range(intentos):
        bal=0.0; alto=0.0; mll=-2000.0; bloq=False; mejor=0.0
        for d in range(max_dias):
            r,peor = dia(rng.integers(len(C)), n, meta, freno)
            dias_tot += 1
            if bal+peor <= mll or bal+r <= mll: break
            bal+=r; mejor=max(mejor,r)
            if not bloq:
                alto=max(alto,bal); mll=alto-2000
                if bal>2100: mll=100; bloq=True
            if bal>=3000 and mejor<=0.5*bal: pasa+=1; break
    p=pasa/intentos; dpi=dias_tot/intentos
    return p, dpi
print('\nMNQ c/u | meta diaria | freno diario | pasa por intento | días por intento | días hasta fondearte (promedio) | exámenes ($90) hasta fondearte')
res=[]
for n in (1,2,3,4,5,6,8,10):
    for meta in (None, 1550):
        for freno in (None, 600, 900, 1200):
            p,dpi = examen(n,meta,freno)
            if p>0: res.append((dpi/p, 90/p, n, meta, freno, p, dpi))
res.sort()
for r in res[:15]:
    dias, costo, n, meta, freno, p, dpi = r
    print(f"{n:>4} | {('+$'+str(meta)) if meta else 'sin meta':>9} | {('-$'+str(freno)) if freno else 'sin freno':>9} | {p:5.0%} | {dpi:4.1f} | {dias:5.1f} | {costo/90:4.1f} (${costo:,.0f})")
print('\nReferencia (1 MNQ, sin meta ni freno):')
p,dpi=examen(1,None,None); print(f'pasa {p:.0%} · {dpi:.1f} días por intento · {dpi/p:.1f} días hasta fondearte · {1/p:.1f} exámenes')
