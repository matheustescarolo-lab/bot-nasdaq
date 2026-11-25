"""AUDIT_014 · pruebas de sobreajuste del bot (Claude, 24-nov). Corre sobre una copia con historia_nas_dukascopy.csv, extra/ y todo_pesos.pkl (de todo.py).
1) desnudo vs reglas de ejecución vs bot completo, por año · 2) rejilla de configuraciones (ORB BE×sacudida, ruido escalera×stop, 8 capas on/off)
3) walk-forward por mitades · 4) PBO por CSCV (16 bloques) · 5) Deflated Sharpe · 6) costos ×2, sin los mejores días, bootstrap por bloques
7) Dukascopy vs Tickmill (bróker real) en las mismas fechas."""
import itertools, pickle, os, numpy as np, pandas as pd, reglas as R
from scipy.stats import norm, skew, kurtosis
arr, K, f = R.arr, R.K, R.fechas; h1, h2 = R.h1, R.h2
sh = lambda x: x.mean()/x.std(ddof=1)*np.sqrt(252) if x.std() > 0 else 0.0

def orb_p(g, be, sac):                                   # = R.orb_x con nivel de BE y sacudida como parámetros
    o, h, l, c = g.o, g.h, g.l, g.c; hi, lo = h[:6].max(), l[:6].min(); regla = dict(tipo='be', activa=be) if be else None
    for i in range(6, R.CIERRE+1):
        up, dn = h[i] > hi, l[i] < lo
        if up and dn:
            s = 1 if abs(o[i]-hi) <= abs(o[i]-lo) else -1
            return [(s, max(hi, o[i]) if s == 1 else min(lo, o[i]), lo if s == 1 else hi, i, i)]
        if up or dn:
            s = 1 if up else -1; st = lo if up else hi; e = max(hi, o[i]) if up else min(lo, o[i])
            if (s == 1 and c[i] <= st) or (s == -1 and c[i] >= st): return [(s, e, st, i, i)]
            if sac and s*(c[i]/c[i-1]-1) < -sac: return [(s, e, c[i], i, i)]
            maxp = max(0, (c[i]-e)*s*R.USD)
            for j in range(i+1, R.CIERRE+1):
                x, maxp = R.gestiona(s, e, j, g, st, None, regla, maxp)
                if x is not None: return [(s, e, x, i, j)]
                if sac and s*(c[j]/c[j-1]-1) < -sac: return [(s, e, c[j], i, j)]
            return [(s, e, c[R.CIERRE], i, R.CIERRE)]
    return []
pnl = lambda trs, cost: sum(s*(x-e)*R.USD - cost for s, e, x, a, b in trs)

def orb_vec(be, sac, fed=True, cost=3):
    return np.array([0.0 if (fed and pd.Timestamp(arr[k].d) in R.FOMC) else pnl(orb_p(arr[k], be, sac), cost) for k in K])
def ruido_vec(esc, stop, cost=4):
    out = []
    for k in K:
        hist = [np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14, k)]
        out.append(pnl(R.ruido_x(arr[k], hist, arr[k-1].c[-1], esc, stop), cost))
    return np.array(out)

def dia(o, r, mo, mr):                                   # $/día por MNQ base, redondeo como el bot
    return (np.round(6*mo)*o + np.round(6*mr)*r)/6

CACHE = 'sobre_cache.pkl'
if os.path.exists(CACHE): O, Rr = pickle.load(open(CACHE, 'rb'))
else:
    O = {(be, sac): orb_vec(be, sac) for be in (None, 75, 150, 300) for sac in (None, 0.004, 0.006, 0.008)}
    O['desnudo'] = orb_vec(None, None, fed=False); O['x2'] = orb_vec(150, 0.006, cost=6)
    Rr = {(esc, st): ruido_vec(esc, st) for esc in (False, True) for st in (None, 0.01, 0.025)}
    Rr['x2'] = ruido_vec(True, 0.01, cost=8)
    pickle.dump((O, Rr), open(CACHE, 'wb'))
uno = np.ones(len(K)); MO, MR = R.pesos()
full = dia(O[(150, 0.006)], Rr[(True, 0.01)], MO, MR)
naked = dia(O['desnudo'], Rr[(False, None)], uno, uno)
ejec = dia(O[(150, 0.006)], Rr[(True, 0.01)], uno, uno)
print(f"1) $/día por MNQ base · Sharpe anual")
for nom, x in (('desnudo (sin BE/sacudida/Fed/escalera/stop, sin capas)', naked), ('+ reglas de ejecución, sin capas', ejec), ('bot completo', full)):
    print(f"   {nom:55} todo {x.mean():5.1f} ({sh(x):.2f}) · 2019–22 {x[h1].mean():5.1f} ({sh(x[h1]):.2f}) · 2023–26 {x[h2].mean():5.1f} ({sh(x[h2]):.2f})")
yrs = f.year.values
print('   por año (desnudo / ejecución / completo):', ' · '.join(f"{y}: {naked[yrs==y].mean():.0f}/{ejec[yrs==y].mean():.0f}/{full[yrs==y].mean():.0f}" for y in range(2019, 2027)))

# 2) rejilla
capas = ('vol', 'r9', 'cot', 'gig', 'nfp', 'caida', 'pay', 'tope')
P = {}
for sub in itertools.product((0, 1), repeat=len(capas)):
    sin = tuple(c for c, on in zip(capas, sub) if not on); P[sub] = R.pesos(sin)
cfg, M = [], []
for ok in [k for k in O if isinstance(k, tuple)]:
    for rk in [k for k in Rr if isinstance(k, tuple)]:
        for sub, (mo, mr) in P.items():
            cfg.append((ok, rk, sub)); M.append(dia(O[ok], Rr[rk], mo, mr))
M = np.array(M); N = len(M); i_bot = cfg.index(((150, 0.006), (True, 0.01), (1,)*8))
S_all = M.mean(1)/M.std(1, ddof=1)*np.sqrt(252)
print(f"2) rejilla: {N} configuraciones · Sharpe del bot {S_all[i_bot]:.2f} · percentil del bot en la rejilla {np.mean(S_all < S_all[i_bot]):.0%} · mediana {np.median(S_all):.2f} · máx {S_all.max():.2f}")

# 3) walk-forward
for nom, tr, te in (('elige con 2019–22 → prueba 2023–26', h1, h2), ('elige con 2023–26 → prueba 2019–22', h2, h1)):
    s_tr = M[:, tr].mean(1)/M[:, tr].std(1, ddof=1); b = s_tr.argmax(); x = M[b, te]; xb = M[i_bot, te]
    rk = np.mean(M[:, te].mean(1)/M[:, te].std(1, ddof=1) < x.mean()/x.std(ddof=1))
    print(f"3) {nom}: elegido {cfg[b][0]}, ruido {cfg[b][1]}, capas {''.join(map(str, cfg[b][2]))} → prueba ${x.mean():.1f}/día Sharpe {sh(x):.2f} (percentil {rk:.0%}) · el bot actual en esa mitad ${xb.mean():.1f} Sharpe {sh(xb):.2f} · elegido en entrenamiento ${M[b, tr].mean():.1f} Sharpe {sh(M[b, tr]):.2f}")

# 4) PBO por CSCV
S = 16; blq = np.array_split(np.arange(len(K)), S)
sm = np.stack([M[:, b].sum(1) for b in blq], 1); sq = np.stack([(M[:, b]**2).sum(1) for b in blq], 1); nb = np.array([len(b) for b in blq])
lam = []
for comb in itertools.combinations(range(S), S//2):
    a = np.zeros(S, bool); a[list(comb)] = True
    def shr(m):
        n = nb[m].sum(); s1 = sm[:, m].sum(1); s2 = sq[:, m].sum(1); mu = s1/n
        return mu/np.sqrt(np.maximum(s2/n - mu**2, 1e-12))
    si, so = shr(a), shr(~a); b = si.argmax(); w = (so < so[b]).mean() + 0.5/N
    lam.append(np.log(w/(1-w)))
lam = np.array(lam)
print(f"4) PBO (CSCV, {S} bloques, {len(lam)} particiones, {N} configs): {np.mean(lam <= 0):.0%} · logit mediano {np.median(lam):+.2f}")

# 5) Deflated Sharpe (Bailey y López de Prado 2014), Sharpe diario
sr = full.mean()/full.std(ddof=1); T = len(full); g3 = skew(full); g4 = kurtosis(full, fisher=False)
def dsr(n, var):
    em = np.sqrt(var)*((1-0.5772)*norm.ppf(1-1/n) + 0.5772*norm.ppf(1-1/(n*np.e)))
    return norm.cdf((sr-em)*np.sqrt(T-1)/np.sqrt(1 - g3*sr + (g4-1)/4*sr**2)), em*np.sqrt(252)
v_emp = (S_all/np.sqrt(252)).var(ddof=1); v0 = 1/(T-1)
print(f"5) Deflated Sharpe · Sharpe anual {sr*np.sqrt(252):.2f}, asimetría {g3:.2f}, curtosis {g4:.1f}")
for n in (50, 200, 500, 2000):
    p1, e1 = dsr(n, v0); p2, e2 = dsr(n, v_emp)
    print(f"   N={n:5}: DSR {p1:.3f} (umbral de azar {e1:.2f}) · con la varianza real de la rejilla {p2:.3f} (umbral {e2:.2f})")

# 6) sensibilidad
x2 = dia(O['x2'], Rr['x2'], MO, MR); print(f"6) costos ×2: ${x2.mean():.1f}/día (Sharpe {sh(x2):.2f}) · 2019–22 {x2[h1].mean():.1f} · 2023–26 {x2[h2].mean():.1f}")
for q in (0.01, 0.05):
    corte = np.quantile(full, 1-q); y = full[full < corte]; print(f"   sin el mejor {q:.0%} de los días: ${y.mean():.1f}/día (Sharpe {sh(y):.2f})")
rng = np.random.default_rng(0); L = 20; nbk = len(full)//L
bs = [np.concatenate([full[s:s+L] for s in rng.integers(0, len(full)-L, nbk)]).mean() for _ in range(5000)]
print(f"   bootstrap por bloques de 20 días: ${np.mean(bs):.1f}/día · IC 90% [{np.quantile(bs, .05):.1f}, {np.quantile(bs, .95):.1f}] · P(≤ 0) {np.mean(np.array(bs) <= 0):.1%}")
for nm, sel in (('BE', lambda c: c[0][0]), ('sacudida', lambda c: c[0][1])):
    vals = sorted({str(sel(c)) for c in cfg}); todos = np.array([str(sel(c)) for c in cfg]); capas_on = np.array([c[2] == (1,)*8 and c[1] == (True, 0.01) for c in cfg])
    print(f"   meseta {nm} (resto como el bot):", ' · '.join(f"{v}: {M[(todos == v) & capas_on & np.array([c[0][1 if nm == 'BE' else 0] == (0.006 if nm == 'BE' else 150) for c in cfg])].mean():.1f}" for v in vals))
pickle.dump(dict(full=full, naked=naked, ejec=ejec, fechas=f), open('sobre_series.pkl', 'wb'))
