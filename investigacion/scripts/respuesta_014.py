"""AUDIT_014 · respuesta de Claude a Neon (24-nov). Corre en una COPIA, en la misma carpeta y con los mismos datos que sobreajuste.py,
después de él (usa sobre_cache.pkl y sobre_series.pkl) y de todo.py (todo_pesos.pkl). No cambia ninguna regla: solo mide.
1) P&L normalizado por precio (bps del nocional de 1 MNQ) · 2) efecto MARGINAL de las capas (bot completo − sin capas) con N efectiva
3) PBO solo entre las 256 combinaciones de capas (núcleo fijo) · 4) costos de 6–8 pts en ruido · 5) Dukascopy vs Tickmill mismas fechas
6) correcciones de datos: VWAP con volumen < 1, FOMC sin el recorte de emergencia, gigantes sin PLTR/AMD y día hábil real, COT +7 días."""
import inspect, itertools, pickle, numpy as np, pandas as pd, reglas as R
from scipy.stats import norm, skew, kurtosis
arr, K, f = R.arr, R.K, R.fechas; h1, h2 = R.h1, R.h2; yrs = f.year.values
O, Rr = pickle.load(open('sobre_cache.pkl', 'rb'))
S = pickle.load(open('sobre_series.pkl', 'rb')); full, ejec, naked = S['full'], S['ejec'], S['naked']
sh = lambda x: x.mean()/x.std(ddof=1)*np.sqrt(252) if x.std() > 0 else 0.0
tt = lambda x: x.mean()/x.std(ddof=1)*np.sqrt(len(x)) if x.std() > 0 else 0.0
dia = lambda o, r, mo, mr: (np.round(6*mo)*o + np.round(6*mr)*r)/6
bps = lambda x: x/(2*R.precio)*1e4                      # bps del nocional de 1 MNQ (2 US$/pt × precio de ayer): 2019 y 2026 pesan igual
MO, MR = R.pesos(); uno = np.ones(len(K))
print(f"precio de ayer: 2019 {R.precio[yrs == 2019].mean():,.0f} · 2026 {R.precio[yrs == 2026].mean():,.0f} (×{R.precio[yrs == 2026].mean()/R.precio[yrs == 2019].mean():.1f})")

print("\n1) Normalizado por precio (bps/día del nocional de 1 MNQ) · Sharpe · asimetría · curtosis")
for nom, x in (('desnudo', naked), ('+ ejecución', ejec), ('bot completo', full)):
    b = bps(x); c5 = b[b < np.quantile(b, .95)]
    print(f"   {nom:13} {b.mean():5.2f} bps (Sharpe {sh(b):.2f}; 2019–22 {sh(b[h1]):.2f} · 2023–26 {sh(b[h2]):.2f}) · asim {skew(b):.2f} · curt {kurtosis(b, fisher=False):.1f}"
          f" · sin el mejor 5%: {c5.mean():+.2f} bps · por año: " + ' '.join(f"{y % 100}:{b[yrs == y].mean():+.1f}" for y in range(2019, 2027)))

print("\n2) Efecto MARGINAL de las capas (bot completo − ejecución sin capas), por día")
m = full - ejec; mb = bps(m)
print(f"   US$ {m.mean():+.2f}/día (t {tt(m):+.2f}) · bps {mb.mean():+.2f}/día (t {tt(mb):+.2f}; 2019–22 t {tt(mb[h1]):+.2f} · 2023–26 t {tt(mb[h2]):+.2f})")
print("   por año US$:", ' '.join(f"{y % 100}:{m[yrs == y].mean():+.0f}" for y in range(2019, 2027)), "· bps:", ' '.join(f"{y % 100}:{mb[yrs == y].mean():+.2f}" for y in range(2019, 2027)))
for n in (100, 300):
    em = (1-0.5772)*norm.ppf(1-1/n) + 0.5772*norm.ppf(1-1/(n*np.e))         # máximo esperado de n estadísticos t nulos e independientes
    print(f"   N efectiva {n}: un t de azar llega a ~{em:.2f} → t del conjunto de capas en bps {tt(mb):.2f} {'PASA' if tt(mb) > em else 'NO pasa'}")
capas = ('vol', 'r9', 'cot', 'gig', 'nfp', 'caida', 'pay', 'tope')
fila = []
for c in capas:
    mo, mr = R.pesos((c,)); d = bps(full - dia(O[(150, 0.006)], Rr[(True, 0.01)], mo, mr))
    fila.append(f"{c} {d.mean():+.2f} (t {tt(d):+.1f}; {tt(d[h1]):+.1f}/{tt(d[h2]):+.1f})")
print("   cada capa (tenerla − no tenerla, bps/día, t total; t 1.ª/2.ª mitad):\n     " + ' · '.join(fila))

print("\n3) PBO solo entre capas (núcleo = ejecución del bot fijo; 256 combinaciones; bps)")
P = [R.pesos(tuple(c for c, on in zip(capas, sub) if not on)) for sub in itertools.product((0, 1), repeat=8)]
M = np.array([bps(dia(O[(150, 0.006)], Rr[(True, 0.01)], mo, mr)) for mo, mr in P])
M = np.unique(M, axis=0); N = len(M)                     # sin filas repetidas (tope inactivo, etc.)
blq = np.array_split(np.arange(len(K)), 16); lam = []
for comb in itertools.combinations(range(16), 8):
    a = np.zeros(len(K), bool); a[np.concatenate([blq[i] for i in comb])] = True
    si = M[:, a].mean(1)/M[:, a].std(1); so = M[:, ~a].mean(1)/M[:, ~a].std(1); b = si.argmax()
    w = (so < so[b]).mean() + 0.5/N; lam.append(np.log(w/(1-w)))
lam = np.array(lam); Sb = M.mean(1)/M.std(1)*np.sqrt(252); i_bot = np.argmin(np.abs(M - bps(full)).sum(1))
print(f"   {N} combinaciones distintas · PBO {np.mean(lam <= 0):.0%} · logit mediano {np.median(lam):+.2f} · bot en percentil {np.mean(Sb < Sb[i_bot]):.0%} (Sharpe {Sb[i_bot]:.2f}; mediana {np.median(Sb):.2f}; sin capas {sh(bps(ejec)):.2f})")

print("\n4) Costos: ruido con 6 y 8 pts ida y vuelta (se suponía 2), ORB 1.5 o 3 pts")
r6 = np.array([sum([s*(x-e)*R.USD - 12 for s, e, x, a, b in R.ruido_x(arr[k], [np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14, k)], arr[k-1].c[-1], True, 0.01)]) for k in K])
ntr = (Rr[(True, 0.01)] - r6)/8                         # operaciones de ruido por día
for nom, o, rpts in (('ORB 1.5 · ruido 2 (como se declaró)', O[(150, 0.006)], 2), ('ORB 1.5 · ruido 6', O[(150, 0.006)], 6),
                     ('ORB 3 · ruido 6', O['x2'], 6), ('ORB 3 · ruido 8', O['x2'], 8)):
    r = Rr[(True, 0.01)] - ntr*(rpts-2)*R.USD; x = dia(o, r, MO, MR)
    print(f"   {nom:36} completo ${x.mean():5.1f}/día (Sharpe {sh(x):.2f}; 2019–22 {x[h1].mean():.1f} · 2023–26 {x[h2].mean():.1f}) · solo ruido sin capas ${r.mean():5.1f}/día")
print(f"   operaciones de ruido por día: {ntr.mean():.2f}")

print("\n5) Dukascopy vs Tickmill (bróker real) en las mismas fechas, mismas reglas y costos")
T = pd.read_csv('historia_ustec_m5.csv', parse_dates=['ny']).set_index('ny'); at = []
for d, g in T.groupby(T.index.date):
    if len(g) < 70 or g.index[0].strftime('%H:%M') != '09:30': continue
    idx = pd.date_range(pd.Timestamp(d)+pd.Timedelta(hours=9, minutes=30), periods=78, freq='5min')
    g = g.reindex(idx); g['close'] = g.close.ffill(); g['tick_volume'] = g.tick_volume.fillna(0)
    for k in ['open', 'high', 'low']: g[k] = g[k].fillna(g.close)
    x = type('G', (), {})(); x.o, x.h, x.l, x.c, x.v = (g[k].values for k in ['open', 'high', 'low', 'close', 'tick_volume']); x.d = d; at.append(x)
pos = {pd.Timestamp(arr[k].d): i for i, k in enumerate(K)}; filas = []
for k in range(14, len(at)):
    g = at[k]; ts = pd.Timestamp(g.d)
    if ts not in pos: continue
    i = pos[ts]; fed = ts in R.FOMC
    to = [] if fed else R.orb_x(g); tr = R.ruido_x(g, [np.abs(at[j].c/at[j].o[0]-1) for j in range(k-14, k)], at[k-1].c[-1], True, 0.01)
    od = [] if fed else R.orb_x(arr[K[i]])
    filas.append(dict(fecha=ts, o_t=sum(s*(x-e)*R.USD-3 for s, e, x, a, b in to), r_t=sum(s*(x-e)*R.USD-4 for s, e, x, a, b in tr),
                      o_d=O[(150, 0.006)][i], r_d=Rr[(True, 0.01)][i], lado_t=to[0][0] if to else 0, lado_d=od[0][0] if od else 0,
                      n_t=len(tr), mo=MO[i], mr=MR[i]))
C = pd.DataFrame(filas)
ct = dia(C.o_t.values, C.r_t.values, C.mo.values, C.mr.values); cd = dia(C.o_d.values, C.r_d.values, C.mo.values, C.mr.values)
print(f"   {len(C)} días ({C.fecha.min().date()} → {C.fecha.max().date()})")
for nom, a, b in (('ORB sin capas', C.o_t, C.o_d), ('Ruido sin capas', C.r_t, C.r_d), ('Bot completo', ct, cd)):
    a, b = np.asarray(a), np.asarray(b)
    print(f"   {nom:16} Tickmill ${a.mean():6.1f}/día (Sharpe {sh(a):.2f}) · Dukascopy ${b.mean():6.1f}/día (Sharpe {sh(b):.2f}) · correlación diaria {np.corrcoef(a, b)[0, 1]:.2f}")
print(f"   ORB mismo lado (o ambos sin operar): {(C.lado_t == C.lado_d).mean():.0%} de los días · ruido opera (o no) el mismo día en ambos: {((C.r_t != 0) == (C.r_d != 0)).mean():.0%}")

print("\n6) Correcciones de datos señaladas por Neon (efecto en el bot completo, $/día)")
assert 'np.maximum(np.cumsum(v), 1)' in inspect.getsource(R.ruido_x)
src = inspect.getsource(R.ruido_x).replace('np.maximum(np.cumsum(v), 1)', 'np.maximum(np.cumsum(v), 1e-9)').replace('def ruido_x', 'def ruido_v')
exec(src, R.__dict__)
rv = np.array([sum(s*(x-e)*R.USD - 4 for s, e, x, a, b in R.ruido_v(arr[k], [np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14, k)], arr[k-1].c[-1], True, 0.01)) for k in K])
x = dia(O[(150, 0.006)], rv, MO, MR); print(f"   VWAP sin el piso de volumen 1: ${x.mean():.2f}/día (antes {full.mean():.2f}) · días que cambian {(rv != Rr[(True, 0.01)]).sum()}")
o2 = O[(150, 0.006)].copy(); i = list(f).index(pd.Timestamp('2020-03-03')); o2[i] = sum(s*(x-e)*R.USD-3 for s, e, x, a, b in R.orb_x(arr[K[i]]))
x = dia(o2, Rr[(True, 0.01)], MO, MR); print(f"   ORB opera el 3-mar-2020 (recorte de emergencia, no programado): ${x.mean():.2f}/día (ese día ORB {o2[i]:+.0f} US$ por MNQ)")
W0 = R.W.copy(); G = pd.read_csv('reportes_gigantes.csv', parse_dates=['fecha']); dias = pd.DatetimeIndex(f)
def gig_set(g):
    out = set()
    for _, r in g.iterrows():
        if r.simbolo == 'ASML': out.add(r.fecha)
        else:
            j = dias.searchsorted(r.fecha, side='right')
            if j < len(dias): out.add(dias[j])
    return out
for nom, g in (('gigantes: siguiente día HÁBIL de bolsa (feriados)', G), ('gigantes sin PLTR ni AMD (no eran gigantes en 2019)', G[~G.simbolo.isin(['PLTR', 'AMD'])]),
               ('gigantes solo los 7 de siempre (AAPL MSFT AMZN GOOGL/GOOG META NVDA TSLA)', G[G.simbolo.isin(['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'GOOG', 'META', 'NVDA', 'TSLA'])])):
    R.W = W0.copy(); R.W['gig'] = dias.isin(list(gig_set(g))); mo, mr = R.pesos(); x = dia(O[(150, 0.006)], Rr[(True, 0.01)], mo, mr)
    mo0, mr0 = R.pesos(('gig',)); d = bps(x - dia(O[(150, 0.006)], Rr[(True, 0.01)], mo0, mr0))
    print(f"   {nom}: ${x.mean():.2f}/día · capa gigantes {d.mean():+.2f} bps/día (t {tt(d):+.1f}; {tt(d[h1]):+.1f}/{tt(d[h2]):+.1f})")
R.W = W0.copy()
c = pd.read_csv('extra/cot_nasdaq.csv', low_memory=False, parse_dates=['Report_Date_as_YYYY-MM-DD']); c = c[c.Market_and_Exchange_Names.str.contains('Consolidated')]
c['Report_Date_as_YYYY-MM-DD'] = c['Report_Date_as_YYYY-MM-DD'].astype('datetime64[ns]')
c = c.groupby('Report_Date_as_YYYY-MM-DD')[['Lev_Money_Positions_Long_All', 'Lev_Money_Positions_Short_All', 'Open_Interest_All']].sum().sort_index()
c['dlev'] = ((c.iloc[:, 0]-c.iloc[:, 1])/c.Open_Interest_All).diff(); c.index = c.index + pd.Timedelta(days=7)
R.W['cot'] = np.where(pd.merge_asof(pd.DataFrame(index=dias), c[['dlev']].dropna(), left_index=True, right_index=True).dlev < -0.0259, 0.5, 1.0)
mo, mr = R.pesos(); x = dia(O[(150, 0.006)], Rr[(True, 0.01)], mo, mr); R.W = W0
print(f"   COT un día más tarde (+7 días: nunca antes de publicarse, aun con feriado): ${x.mean():.2f}/día · días con otro peso {(np.abs(mo - MO) > 0).sum()}")
