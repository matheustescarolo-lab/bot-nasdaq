"""Juez diario de la prueba en papel de MNQ (rango de 30 min + zona de ruido), con protección de ganancias desde el 18-nov-2026:
  - Rango 30 min: break even (el stop pasa al precio de entrada) cuando la operación llega a ir +US$150.
  - Zona de ruido: escalera — al llegar a +US$200 asegura +US$100, y cada US$100 más sube el piso US$100.
Uso: python3 mnq_diario.py velas_qqq_5min.txt   (archivo de Twelve Data: QQQ, 5min, outputsize 1500, separado por ';')
Imprime, para cada uno de los últimos 10 días, qué señales dio cada estrategia y el resultado en US$ con 1 MNQ (con costos)."""
import sys, numpy as np, pandas as pd
K, PV, COSTO = 41.2, 2.0, 2.5
USD = K * PV                                   # US$ por punto de QQQ con 1 MNQ
BE_ORB, ESC_DESDE, ESC = 150, 200, 100
CIERRE = 76                                    # vela de 15:50–15:55: el bot cierra a las 15:55 (2:55 pm CDMX)
D = pd.read_csv(sys.argv[1], sep=';', parse_dates=['datetime']).set_index('datetime').sort_index()
D = D[(D.index.time >= pd.Timestamp('09:30').time()) & (D.index.time <= pd.Timestamp('15:55').time())]
DIAS = []
for d, g in D.groupby(D.index.date):
    if len(g) < 70: continue
    idx = pd.date_range(pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=30), periods=78, freq='5min')
    g = g.reindex(idx); g['close'] = g.close.ffill(); g['volume'] = g.volume.fillna(0)
    for k in ('open', 'high', 'low'): g[k] = g[k].fillna(g.close)
    DIAS.append((pd.Timestamp(d), g.open.values, g.high.values, g.low.values, g.close.values, g.volume.values, g.index))

def piso(clave, maxp):
    if clave == 'orb': return 0.0 if maxp >= BE_ORB else None
    return (maxp // ESC) * ESC - ESC if maxp >= ESC_DESDE else None

def revisa(clave, s, e, j, o, h, l, stop, maxp):
    """Vela j con la posición abierta: primero el stop/piso (conservador). Devuelve (precio de salida o None, maxp)."""
    niv = [x for x in (stop, None if piso(clave, maxp) is None else e + s * piso(clave, maxp) / USD) if x is not None]
    if niv:
        m = max(niv) if s == 1 else min(niv)
        if (s == 1 and l[j] <= m) or (s == -1 and h[j] >= m):
            return (min(m, o[j]) if s == 1 else max(m, o[j])), maxp
    return None, max(maxp, ((h[j] - e) if s == 1 else (e - l[j])) * USD)

def orb30(o, h, l, c):
    hi, lo = h[:6].max(), l[:6].min()
    for i in range(6, CIERRE + 1):
        up, dn = h[i] > hi, l[i] < lo
        if up and dn: return [], hi, lo
        if up or dn:
            s = 1 if up else -1; st = lo if up else hi; e = max(hi, o[i]) if up else min(lo, o[i])
            if (s == 1 and c[i] <= st) or (s == -1 and c[i] >= st): return [(s, e, st, i, i)], hi, lo
            maxp = max(0, (c[i] - e) * s * USD)
            for j in range(i + 1, CIERRE + 1):
                x, maxp = revisa('orb', s, e, j, o, h, l, st, maxp)
                if x is not None: return [(s, e, x, i, j)], hi, lo
            return [(s, e, c[CIERRE], i, CIERRE)], hi, lo
    return [], hi, lo

def ruido(look=14):
    mov, out, prev = {}, {}, None
    for k, (d, o, h, l, c, v, ix) in enumerate(DIAS):
        op = o[0]; m = np.abs(c / op - 1)
        if k >= look and prev is not None:
            hist = [mov[j] for j in range(k - look, k)]
            sig = np.array([np.mean([x[i] for x in hist]) for i in range(len(c))])
            ub = max(op, prev) * (1 + sig); lb = min(op, prev) * (1 - sig)
            vw = np.cumsum((h + l + c) / 3 * v) / np.maximum(np.cumsum(v), 1)
            pos, e, ie, trs, maxp = 0, 0, 0, [], 0
            for i in range(CIERRE):
                if pos and i > ie:
                    x, maxp = revisa('ruido', pos, e, i, o, h, l, None, maxp)
                    if x is not None: trs.append((pos, e, x, ie, i)); pos = 0
                t = ix[i]
                if not (t.minute in (25, 55) and (t.hour, t.minute) >= (9, 55)): continue
                antes = pos
                if pos == 1 and c[i] < max(ub[i], vw[i]): trs.append((1, e, c[i], ie, i)); pos = 0
                elif pos == -1 and c[i] > min(lb[i], vw[i]): trs.append((-1, e, c[i], ie, i)); pos = 0
                if pos == 0:
                    s = 1 if c[i] > ub[i] else -1 if c[i] < lb[i] else 0
                    if s and antes == s:              # salir y volver a entrar del mismo lado = quedarse adentro
                        t0 = trs.pop(); pos, e, ie = s, t0[1], t0[3]
                    elif s: pos, e, ie, maxp = s, c[i], i, 0
            if pos: trs.append((pos, e, c[CIERRE], ie, CIERRE))
            out[d] = trs
        mov[k] = m; prev = c[-1]
    return out

hora = lambda ix, i: (ix[i] + pd.Timedelta(minutes=5) - pd.Timedelta(hours=1)).strftime('%H:%M')   # cierre de la vela, en hora de CDMX (invierno)
R = ruido(); tot = {'orb30': 0.0, 'ruido': 0.0}
for d, o, h, l, c, v, ix in DIAS[-10:]:
    t1, hi, lo = orb30(o, h, l, c); t2 = R.get(d, [])
    p1 = sum(s * (x - e) * USD - COSTO for s, e, x, a, b in t1); p2 = sum(s * (x - e) * USD - COSTO for s, e, x, a, b in t2)
    tot['orb30'] += p1; tot['ruido'] += p2
    f = lambda trs: '; '.join(f"{'compra' if s == 1 else 'venta'} {hora(ix, a)}→{hora(ix, b)}" for s, e, x, a, b in trs) or 'sin señal'
    print(f"{d:%a %d-%b} | rango 30m (QQQ) {hi:.2f}/{lo:.2f} | ORB30: {f(t1)} = ${p1:+.0f} | Ruido: {f(t2)} = ${p2:+.0f}")
print(f"Total 10 días (1 MNQ c/u, con costos, break even + escalera): ORB30 ${tot['orb30']:+.0f} · Ruido ${tot['ruido']:+.0f}")
