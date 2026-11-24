"""freno_v4: como freno_v3 + (AUDIT_011) solo cuentan días CON operaciones para el mínimo de 4, y si el deslizamiento del freno
llega al límite es quema. Pregunta de Neon: agotado 2% solo en el reto y 0.8% en la fondeada."""
import numpy as np
exec(open("freno_v3.py").read().split("if __name__")[0])
SLIP = 2.0
def hacer(col):
    def d(k, base, C, meta, room, fijo=False):
        Co, Wo, Cr, Wr = C
        no, nr = ((1 if MO[k] > 0 else 0), (1 if MR[k] > 0 else 0)) if fijo else (round(base*MO[k]), round(base*MR[k])); m = no+nr
        if m == 0: return 0.0, False, False
        fr = room - col(m)
        if fr <= 0: return 0.0, False, False
        c = no*Co[k]+nr*Cr[k]; w = no*Wo[k]+nr*Wr[k]
        q = np.flatnonzero(w <= -room); f = np.flatnonzero(w <= -fr)
        g = np.flatnonzero(c >= meta) if meta is not None else np.array([], int)
        t = min([x[0] for x in (q, f, g) if len(x)]+[99])
        if t == 99: return c[-1], False, True
        if len(f) and f[0] == t:
            r = -fr-SLIP*2*m
            return (-room, True, True) if r <= -room else (r, False, True)
        if len(q) and q[0] == t: return -room, True, True
        return c[t], False, True
    return d
def dos_pasos4(s, C, nmax, dia, ag_r, ag_f, bc=6, bf=4, fee=439, H=252):
    pago = 0; compras = 0; reemb = 0; est = None
    for k in range(s, min(s+H, len(fechas))):
        if est in (None, 'x'):
            if compras >= nmax: break
            est = 'p1'; bal = 0.0; dias = 0; compras += 1; df = 0; reemb_ok = True
        if est in ('p1', 'p2'):
            mf = (0.10 if est == 'p1' else 0.05)*1e5
            if bal >= mf: r, q, op = dia(k, bc, C, 50.0, min(5000, bal+10000), fijo=True)   # meta lograda: 1 MNQ y meta $50 hasta los 4 días
            else: r, q, op = dia(k, bc, C, max(mf-bal, 100), min(5000, bal+10000))
            if q: est = 'x'; continue
            bal += r; dias += op
            if bal+10000 < ag_r: est = 'x'; continue
            if bal >= mf and dias >= 4: est = 'p2' if est == 'p1' else 'f'; bal = 0.0; dias = 0
        else:
            r, q, op = dia(k, bf, C, None, min(5000, bal+10000))
            if q: est = 'x'; continue
            bal += r; df += 1
            if bal+10000 < ag_f: est = 'x'; continue
            if df % 10 == 0 and bal > 0:
                pago += 0.8*bal; bal = 0.0
                if reemb_ok: reemb += 1; reemb_ok = False
    return pago-(compras-reemb)*fee*EUR, pago > 0, compras
if __name__ == '__main__':
    dd = hacer(lambda m: max(400, 60*m))
    for mit, nom in ((False, 'pruebas'), (True, 'mitad')):
        C = caminos(mit); print('==', nom, flush=True)
        for etq, ar, af in (('agotado 0.8% en todo (antes)', 800, 800), ('agotado 2% en todo (ahora)', 2000, 2000),
                            ('2% en el reto, 0.8% en la fondeada', 2000, 800)):
            print(f"{etq:36}", res3(lambda s: dos_pasos4(s, C, 4, dd, ar, af)), flush=True)
