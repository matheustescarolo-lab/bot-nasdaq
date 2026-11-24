import sys, numpy as np, pandas as pd, datetime as dt
sys.path.insert(0, '/home/claude/bot-nasdaq')
from estrategias import niveles_orb, modelo_orb, modelo_ruido, VELAS_DIA_MIN
D = pd.read_csv('velas.txt', sep=';', parse_dates=['datetime']).set_index('datetime').sort_index()
DIAS = [(pd.Timestamp(d), g.open.values, g.high.values, g.low.values, g.close.values, g.volume.values, g.index)
        for d, g in D.groupby(D.index.date) if len(g) >= 70]
# ---- funciones del juez (mnq_diario.py, sin cambios) ----
def orb30(o, h, l, c):
    hi, lo = h[:6].max(), l[:6].min()
    for i in range(6, len(c)):
        up, dn = h[i] > hi, l[i] < lo
        if up and dn: return [], hi, lo
        if up or dn:
            s = 1 if up else -1; st = lo if up else hi; e = max(hi, o[i]) if up else min(lo, o[i])
            if (s == 1 and c[i] <= st) or (s == -1 and c[i] >= st): return [(s, e, st, i, i)], hi, lo
            for j in range(i + 1, len(c)):
                if (s == 1 and l[j] <= st) or (s == -1 and h[j] >= st):
                    return [(s, e, (min(st, o[j]) if s == 1 else max(st, o[j])), i, j)], hi, lo
            return [(s, e, c[-1], i, len(c) - 1)], hi, lo
    return [], hi, lo
def ruido(look=14):
    mov, out, prev = {}, {}, None
    for k, (d, o, h, l, c, v, ix) in enumerate(DIAS):
        op = o[0]; m = np.abs(c / op - 1)
        if k >= look and prev is not None:
            hist = np.array([mov[j][:len(c)] if len(mov[j]) >= len(c) else np.pad(mov[j], (0, len(c) - len(mov[j])), 'edge') for j in range(k - look, k)])
            sig = hist.mean(0); ub = max(op, prev) * (1 + sig); lb = min(op, prev) * (1 - sig)
            vw = np.cumsum((h + l + c) / 3 * v) / np.maximum(np.cumsum(v), 1)
            pos, e, ie, trs = 0, 0, 0, []
            for i in range(len(c) - 1):
                t = ix[i]
                if not (t.minute in (25, 55) and (t.hour, t.minute) >= (9, 55)): continue
                if pos == 1 and c[i] < max(ub[i], vw[i]): trs.append((1, e, c[i], ie, i)); pos = 0
                elif pos == -1 and c[i] > min(lb[i], vw[i]): trs.append((-1, e, c[i], ie, i)); pos = 0
                if pos == 0:
                    if c[i] > ub[i]: pos, e, ie = 1, c[i], i
                    elif c[i] < lb[i]: pos, e, ie = -1, c[i], i
            if pos: trs.append((pos, e, c[-1], ie, len(c) - 1))
            m2 = []
            for t in trs:
                if m2 and m2[-1][0] == t[0] and m2[-1][4] == t[3]: m2[-1] = (t[0], m2[-1][1], t[2], m2[-1][3], t[4])
                else: m2.append(t)
            out[d] = m2
        mov[k] = m; prev = c[-1]
    return out
R = ruido()
df = D.rename(columns={'open':'o','high':'h','low':'l','close':'c','volume':'v'})
dias = {pd.Timestamp(d): g for d, g in df.groupby(df.index.date)}
claves = sorted(dias)
ok_orb = ok_ru = n_ru = n_orb = 0
for k, d in enumerate(claves):
    hoy = dias[d]; o,h,l,c = hoy.o.values,hoy.h.values,hoy.l.values,hoy.c.values
    # ORB: lado y si terminó en stop, al final del día
    t1, hi, lo = orb30(o,h,l,c)
    lado, est = modelo_orb(hoy, *niveles_orb(hoy))
    jl = t1[0][0] if t1 else 0
    jstop = bool(t1) and t1[0][4] < len(c)-1 or (bool(t1) and t1[0][2] != c[-1])
    if jl == lado: ok_orb += 1
    else: print('ORB distinto', d.date(), jl, lado, est)
    n_orb += 1
    # Ruido: posición del modelo en cada chequeo vs. la del juez
    if d not in R: continue
    previos = [dias[x] for x in claves[:k]][-14:]
    trs = R[d]
    for i, t in enumerate(hoy.index):
        fin = t + dt.timedelta(minutes=5)
        if not (fin.minute in (0,30) and fin.time() >= dt.time(10,0) and fin.time() < dt.time(16,0)): continue
        juez = 0
        for s,e,x,a,b in trs:
            if a <= i < b: juez = s
        mio, _, _ = modelo_ruido(hoy, previos, float(dias[claves[k-1]].c.iloc[-1]), fin.to_pydatetime())
        n_ru += 1
        if mio == juez: ok_ru += 1
        else: print('Ruido distinto', fin, juez, mio)
trades = sum(len(v) for v in R.values())
print(f'ORB: {ok_orb}/{n_orb} días iguales · Ruido: {ok_ru}/{n_ru} chequeos iguales · operaciones de ruido del juez: {trades}')
