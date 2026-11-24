"""Freno FTMO v3 (chat V3, 23-nov): corrige dos cosas del modelo de freno_ab.py
1) si el espacio que queda es menor que el colchón, el día NO opera (antes el freno «cerraba» con ganancia: -fr > 0);
2) regla del bot «agotado»: si quedan < 0.8% antes de la pérdida máxima (equity <= base - 9.2%), la cuenta se da por perdida
   y se compra un reto nuevo (antes quedaba zombi bloqueando la compra).
Salida del freno: en su nivel + 2 pts de deslizamiento. Por mitades de años (inicio del período de 12 meses)."""
import numpy as np, sys
exec(open('productos.py').read().split("import sys")[0])
SLIP = 2.0   # pts por MNQ al salir por freno
def hacer(col, freno_en=('reto', 'fond')):
    def d(k, base, C, meta, room, etapa):
        Co, Wo, Cr, Wr = C; no = round(base*MO[k]); nr = round(base*MR[k]); m = no+nr
        if m == 0: return 0.0, False
        usa = col is not None and etapa in freno_en
        fr = room - (col(m) if usa else 0)
        if usa and fr <= 0: return 0.0, False                    # sin espacio antes del freno: no opera
        c = no*Co[k]+nr*Cr[k]; w = no*Wo[k]+nr*Wr[k]
        q = np.flatnonzero(w <= -room); f = np.flatnonzero(w <= -fr) if usa else np.array([], int)
        g = np.flatnonzero(c >= meta) if meta is not None else np.array([], int)
        t = min([x[0] for x in (q, f, g) if len(x)]+[99])
        if t == 99: return c[-1], False
        if len(f) and f[0] == t: return max(-fr-SLIP*2*m, -room), False
        if len(q) and q[0] == t: return -room, True
        return c[t], False
    return d
def dos_pasos3(s, C, nmax, dia, ag=800, bc=6, bf=4, fee=439, H=252):
    pago = 0; compras = 0; reemb = 0; est = None
    for k in range(s, min(s+H, len(fechas))):
        if est in (None, 'x'):
            if compras >= nmax: break
            est = 'p1'; bal = 0.0; dias = 0; compras += 1; df = 0; reemb_ok = True
        if est in ('p1', 'p2'):
            mf = (0.10 if est == 'p1' else 0.05)*1e5
            r, q = (0.0, False) if bal >= mf else dia(k, bc, C, max(mf-bal, 100), min(5000, bal+10000), 'reto')
            if q: est = 'x'; continue
            bal += r; dias += 1
            if ag and bal+10000 < ag: est = 'x'; continue        # agotado → reto nuevo
            if bal >= mf and dias >= 4: est = 'p2' if est == 'p1' else 'f'; bal = 0.0; dias = 0
        else:
            r, q = dia(k, bf, C, None, min(5000, bal+10000), 'fond')
            if q: est = 'x'; continue
            bal += r; df += 1
            if ag and bal+10000 < ag: est = 'x'; continue
            if df % 10 == 0 and bal > 0:
                pago += 0.8*bal; bal = 0.0
                if reemb_ok: reemb += 1; reemb_ok = False
    return pago-(compras-reemb)*fee*EUR, pago > 0, compras
mid = fechas[len(fechas)//2]
def res3(f):
    A = np.array([f(s) for s in starts]); g = A[:, 0]; h1 = np.array([fechas[s] < mid for s in starts])
    t = lambda m: f"{np.mean(A[m,1]==0):4.0%} ${np.median(g[m]):>7,.0f}"
    return f"no cobra/mediana: todo {t(np.ones(len(g),bool))} · 1.ª mitad {t(h1)} · 2.ª mitad {t(~h1)} · retos {A[:,2].mean():.1f}"
if __name__ == '__main__':
    act = lambda m: max(400, 60*m)
    V = [('sin freno (tocar = quema), agotado 0.8%', None, ('reto', 'fond'), 800),
         ('freno actual + agotado 0.8% (= el bot)', act, ('reto', 'fond'), 800),
         ('freno solo en la fondeada + agotado', act, ('fond',), 800),
         ('freno actual SIN regla de agotado', act, ('reto', 'fond'), 0),
         ('freno actual + agotado 2%', act, ('reto', 'fond'), 2000),
         ('freno actual + agotado 3%', act, ('reto', 'fond'), 3000)]
    for mit, nom in ((False, 'pruebas'), (True, 'mitad')):
        C = caminos(mit); print('==', nom, flush=True)
        for etq, col, en, ag in V:
            dd = hacer(col, en); print(f"{etq:42}", res3(lambda s: dos_pasos3(s, C, 4, dd, ag)), flush=True)
