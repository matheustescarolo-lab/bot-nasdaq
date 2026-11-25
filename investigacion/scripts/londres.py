"""Londres en NAS100 (velas de 1 h, 24 h): (A) ORB de Londres 3:00–4:00 NY, salir a las 9:00 NY; (B) el movimiento de Londres
(3:00→9:00 NY) como filtro del ORB de Nueva York. Costos: 2.5 pts ida y vuelta de madrugada (spread más ancho). 1 MNQ = $2/pt."""
import glob, numpy as np, pandas as pd
import reglas as R
h = pd.concat([pd.read_csv(f) for f in sorted(glob.glob('/home/claude/bot-nasdaq/extra/nas_h1_*.csv'))])
h['t'] = pd.to_datetime(h.timestamp, unit='ms', utc=True).dt.tz_convert('America/New_York'); h = h.set_index('t').sort_index()
h = h[~h.index.duplicated()]
dias = sorted(set(h.index.date)); A, B = [], {}
for d in dias:
    x = h[h.index.date == d]
    if x.index[0].weekday() >= 5: continue
    hr = x.index.hour
    r = x[hr == 3]
    if r.empty: continue
    hi, lo, o3 = r.high.iloc[0], r.low.iloc[0], r.open.iloc[0]
    w = x[(hr >= 4) & (hr <= 8)]; c9 = x[hr == 9].open.iloc[0] if (hr == 9).any() else (w.close.iloc[-1] if len(w) else np.nan)
    if len(w) and not np.isnan(c9):
        res = None
        for _, b in w.iterrows():
            up, dn = b.high > hi, b.low < lo
            if up and dn: res = -(hi - lo); break                           # rompe los dos lados en la misma vela: pérdida
            if up or dn:
                s = 1 if up else -1; e = hi if up else lo; st = lo if up else hi
                resto = w.loc[b.name:]
                toca = (resto.low <= st).any() if s == 1 else (resto.high >= st).any()
                res = -(hi - lo) if toca else s * (c9 - e)
                break
        if res is not None: A.append((pd.Timestamp(d), res * 2 - 2.5 * 2))
    B[pd.Timestamp(d)] = c9 / o3 - 1 if not np.isnan(c9) else np.nan
a = pd.Series(dict(A)).sort_index()
f = lambda s: f"${s.mean():6.1f}/op · t {s.mean()/s.std()*np.sqrt(len(s)):+4.1f} · n {len(s)} · gana {np.mean(s>0):.0%}"
print('A) ORB de Londres (1 MNQ, costos):', f(a))
for nom, m in (('2019–22', a.index < '2023'), ('2023–26', a.index >= '2023'), ('2025–26', a.index >= '2025')): print('   ', nom, f(a[m]))
print('   años:', a.index.max().date())
# B) filtro: ORB NY con el mismo sentido que Londres vs contrario
res = []
for k in R.K:
    g = R.arr[k]; t = R.orb_x(g)
    if not t: continue
    s, e, x = t[0][0], t[0][1], t[0][2]; L = B.get(pd.Timestamp(g.d))
    if L is None or np.isnan(L): continue
    res.append((pd.Timestamp(g.d), s, L, s * (x - e) * 2 - 3))
r = pd.DataFrame(res, columns=['d', 's', 'L', 'p']).set_index('d')
ali = np.sign(r.L) == r.s
print('B) ORB de NY (1 MNQ) según Londres:', 'mismo sentido', f(r.p[ali]), '| contrario', f(r.p[~ali]))
fuerte = r.L.abs() > r.L.abs().median()
print('   Londres fuerte (> mediana):', 'mismo', f(r.p[ali & fuerte]), '| contrario', f(r.p[~ali & fuerte]))
for nom, m in (('2019–22', r.index < '2023'), ('2023–26', r.index >= '2023')):
    print('   ', nom, 'mismo', f(r.p[ali & m]), '| contrario', f(r.p[~ali & m]))
d = r.p[ali].mean() - r.p[~ali].mean(); se = np.sqrt(r.p[ali].var()/ali.sum() + r.p[~ali].var()/(~ali).sum())
print(f'   diferencia mismo − contrario: ${d:.1f}/op · t {d/se:+.1f}')
