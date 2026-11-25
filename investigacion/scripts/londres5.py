"""Londres con velas de 5 min (2:00–9:30 NY). Pruebas fijadas de antemano (3 + 3) para no pescar:
A) ORB de Londres: rango de los primeros 15/30/60 min desde las 8:00 de Londres; orden stop en la ruptura, stop al otro lado,
   salida 9:25 NY. 1 MNQ = $2/pt, costos 2.5 pts ida y vuelta (madrugada).
B) Londres como indicador del ORB de NY: (1) sentido del movimiento de Londres, (2) tamaño del rango de Londres,
   (3) apertura de NY por fuera del rango de Londres en el sentido de la ruptura."""
import numpy as np, pandas as pd, reglas as R
import sys
m = pd.read_csv(sys.argv[1], parse_dates=['ny']).set_index('ny')
if 'spread' in m: print('spread mediano de madrugada (pts):', (m.spread/100).median(), '| 3–4 NY:', (m.spread[m.index.hour==3]/100).median())
f = lambda s: f"${s.mean():6.1f}/op · t {s.mean()/s.std()*np.sqrt(len(s)):+4.1f} · n {len(s)} · gana {np.mean(s>0):.0%}"
dias = {d: g for d, g in m.groupby(m.index.date)}
lon = {}
for d, g in dias.items():
    lo = pd.Timestamp(f'{d} 08:00', tz='Europe/London').tz_convert('America/New_York').tz_localize(None)
    lon[d] = (lo, g)
print('A) ORB de Londres (1 MNQ, con costos):')
for mins in (15, 30, 60):
    out = []
    for d, (lo, g) in lon.items():
        r = g[(g.index >= lo) & (g.index < lo + pd.Timedelta(minutes=mins))]
        w = g[(g.index >= lo + pd.Timedelta(minutes=mins)) & (g.index < pd.Timestamp(f'{d} 09:25'))]
        if len(r) < mins // 5 - 1 or len(w) < 6: continue
        hi, lo_ = r.high.max(), r.low.min(); res = None
        for i, (_, b) in enumerate(w.iterrows()):
            up, dn = b.high > hi, b.low < lo_
            if up and dn: res = -(hi - lo_); break
            if up or dn:
                s = 1 if up else -1; e = hi if up else lo_; st = lo_ if up else hi; resto = w.iloc[i + 1:]
                toca = (resto.low <= st).any() if s == 1 else (resto.high >= st).any()
                res = -(hi - lo_) if toca else s * (w.close.iloc[-1] - e)
                break
        if res is not None: out.append((pd.Timestamp(d), res * 2 - 5))
    a = pd.Series(dict(out)).sort_index()
    print(f'  {mins:>2} min:', f(a), '|', '2019–22', f(a[a.index < '2023']), '|', '2023–26', f(a[a.index >= '2023']))
# B) indicadores para el ORB de NY
res = []
for k in R.K:
    g = R.arr[k]; t = R.orb_x(g)
    dd = pd.Timestamp(g.d).date()
    if not t or dd not in lon: continue
    lo, x = lon[dd]; L = x[(x.index >= lo) & (x.index < pd.Timestamp(f'{dd} 09:30'))]
    if len(L) < 20: continue
    s, e, xx = t[0][0], t[0][1], t[0][2]
    res.append((pd.Timestamp(g.d), s, np.sign(L.close.iloc[-1] - L.open.iloc[0]), (L.high.max() - L.low.min()) / L.close.iloc[-1],
                L.high.max(), L.low.min(), g.o[0], s * (xx - e) * 2 - 3))
r = pd.DataFrame(res, columns=['d', 's', 'sig', 'rng', 'H', 'Lw', 'c', 'p']).set_index('d')
def comp(nom, a):
    d = r.p[a].mean() - r.p[~a].mean(); se = np.sqrt(r.p[a].var() / a.sum() + r.p[~a].var() / (~a).sum())
    print(f'  {nom}: sí {f(r.p[a])} | no {f(r.p[~a])} | dif ${d:5.1f} t {d/se:+.1f}')
print('B) ORB de NY según Londres (todas las operaciones:', f(r.p), ')')
comp('1) Londres va en el sentido de la ruptura', r.sig == r.s)
comp('2) rango de Londres > mediana         ', r.rng > r.rng.median())
comp('3) NY abre fuera del rango de Londres a favor', ((r.s == 1) & (r.c > r.H * 0.9995)) | ((r.s == -1) & (r.c < r.Lw * 1.0005)))
