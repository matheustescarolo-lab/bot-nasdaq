"""Auditoría de reglas (chat V3, 23-nov): bot completo vs el bot sin UNA regla (o con la variante), 8 años Dukascopy.
$/día por MNQ base (base 6, redondeo como el bot), t de la diferencia diaria pareada, por mitades y 2025–2026,
y FTMO 2-Step 4 retos 12 m (freno actual + agotado 0.8%, = el bot) con bot como en pruebas y bot a la mitad."""
import os, re, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
os.environ['ARCH'] = 'historia_nas_dukascopy.csv'
G = {}; exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0], G)
arr, USD, CIERRE, gestiona = G['arr'], G['USD'], G['CIERRE'], G['gestiona']
cal = open('calendario.py').read(); FOMC = set(pd.to_datetime(re.search(r'FOMC="""(.*?)"""', cal, re.S).group(1).split()))
K = range(20, len(arr)); fechas = pd.DatetimeIndex([pd.Timestamp(arr[k].d) for k in K]).astype('datetime64[ns]')

def orb_x(g, be=True, sac=True):
    o, h, l, c = g.o, g.h, g.l, g.c; hi, lo = h[:6].max(), l[:6].min(); regla = dict(tipo='be', activa=150) if be else None
    for i in range(6, CIERRE+1):
        up, dn = h[i] > hi, l[i] < lo
        if up and dn:
            s = 1 if abs(o[i]-hi) <= abs(o[i]-lo) else -1
            return [(s, max(hi, o[i]) if s == 1 else min(lo, o[i]), lo if s == 1 else hi, i, i)]
        if up or dn:
            s = 1 if up else -1; st = lo if up else hi; e = max(hi, o[i]) if up else min(lo, o[i])
            if (s == 1 and c[i] <= st) or (s == -1 and c[i] >= st): return [(s, e, st, i, i)]
            if sac and i > 0 and s*(c[i]/c[i-1]-1) < -0.006: return [(s, e, c[i], i, i)]
            maxp = max(0, (c[i]-e)*s*USD)
            for j in range(i+1, CIERRE+1):
                x, maxp = gestiona(s, e, j, g, st, None, regla, maxp)
                if x is not None: return [(s, e, x, i, j)]
                if sac and s*(c[j]/c[j-1]-1) < -0.006: return [(s, e, c[j], i, j)]
            return [(s, e, c[CIERRE], i, CIERRE)]
    return []

def ruido_x(g, hist, prev, esc=True, stop=None):
    o, h, l, c, v = g.o, g.h, g.l, g.c, g.v; op = o[0]
    sig = np.array([np.mean([m[i] if len(m) > i else m[-1] for m in hist]) for i in range(len(c))])
    ub = max(op, prev)*(1+sig); lb = min(op, prev)*(1-sig)
    vw = np.cumsum((h+l+c)/3*v)/np.maximum(np.cumsum(v), 1)
    pos = 0; e = 0; ie = 0; res = []; maxp = 0; regla = dict(tipo='escalera', activa=200) if esc else None
    for i in range(CIERRE):
        if pos and i > ie:
            st = e*(1-pos*stop) if stop else None
            x, maxp = gestiona(pos, e, i, g, st, None, regla, maxp)
            if x is not None: res.append((pos, e, x, ie, i)); pos = 0
        fin = (i+1)*5+570
        if fin < 600 or fin % 30: continue
        old = pos
        if pos == 1 and c[i] < max(ub[i], vw[i]): res.append((1, e, c[i], ie, i)); pos = 0
        elif pos == -1 and c[i] > min(lb[i], vw[i]): res.append((-1, e, c[i], ie, i)); pos = 0
        if pos == 0:
            s = 1 if c[i] > ub[i] else -1 if c[i] < lb[i] else 0
            if s and old == s: t = res.pop(); pos, e, ie = s, t[1], t[3]
            elif s: pos, e, ie, maxp = s, c[i], i, 0
    if pos: res.append((pos, e, c[CIERRE], ie, CIERRE))
    return res

def caminos(trs, g, cost):
    c = np.zeros(78); w = np.zeros(78)
    for t in range(78):
        vc = vw = 0.0
        for s, e, x, a, b in trs:
            if t > b: r = s*(x-e)*USD-cost; vc += r; vw += r
            elif t >= a: vc += s*(g.c[t]-e)*USD-cost; vw += s*((g.l[t] if s == 1 else g.h[t])-e)*USD-cost
        c[t] = vc; w[t] = vw
    return c, w

def construir(be=True, sac=True, fed=True, costo_orb=3, esc=True, stop_r=None, cost_r=4):
    Co, Wo, Cr, Wr = [], [], [], []
    for k in K:
        g = arr[k]; hist = [np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14, k)]
        to = [] if (fed and pd.Timestamp(g.d) in FOMC) else orb_x(g, be, sac)
        a, b = caminos(to, g, costo_orb); Co.append(a); Wo.append(b)
        a, b = caminos(ruido_x(g, hist, arr[k-1].c[-1], esc, stop_r), g, cost_r); Cr.append(a); Wr.append(b)
    return tuple(np.array(x) for x in (Co, Wo, Cr, Wr))

W = pd.read_pickle('todo_pesos.pkl'); W.index = W.index.astype('datetime64[ns]'); W = W.reindex(fechas)
ret1 = np.array([arr[k-1].c[-1]/arr[k-2].c[-1]-1 for k in K])
pay = np.array([(arr[k-1].c[-1]-arr[k-1].l.min())/max(arr[k-1].h.max()-arr[k-1].l.min(), 1e-9) for k in K])
precio = np.array([arr[k-1].c[-1] for k in K])

def pesos(sin=()):
    vol = np.ones(len(K)) if 'vol' in sin else W.vol.values
    r9 = np.ones(len(K)) if 'r9' in sin else W.r9.values
    cot = np.ones(len(K)) if 'cot' in sin else W.cot.fillna(1).values
    gig = 1.0 if 'gig' in sin else np.where(W.gig.fillna(False).values, 1.5, 1)
    nfp = 1.0 if 'nfp' in sin else np.where(W.nfp.fillna(False).values, 1.5, 1)
    co = 1.0 if 'caida' in sin else np.where(ret1 < -0.02, 0, 1)
    cr = 1.0 if 'caida' in sin else np.where(ret1 < -0.01, 0, 1)
    py = 1.0 if 'pay' in sin else np.where(pay > 0.8, 1.5, np.where(pay < 0.2, 0.5, 1))
    tope = 99.0 if 'tope' in sin else 2.0
    return np.minimum(vol*r9*cot*gig*co, tope), np.minimum(vol*r9*cot*gig*nfp*cr*py, tope)

BASE = 6
def diario(C, MO, MR, mitad=False, margen=False):
    Co, Wo, Cr, Wr = C; no = np.round(BASE*MO); nr = np.round(BASE*MR)
    if margen:                                             # guardia 85% del margen FTMO Swing 1:15 (100K): la que entra después se recorta
        mx = np.floor(0.85*1e5*15/(2*precio))
        nr = np.minimum(nr, np.maximum(mx-no, 0))
    pen = 7.5 if mitad else 0.0
    return (no*(Co[:, -1]-pen*(no > 0)*0+(-pen if mitad else 0)) + nr*(Cr[:, -1]-(pen if mitad else 0)))/BASE, no, nr

h1 = fechas < fechas[len(fechas)//2]; h2 = ~h1; r2526 = fechas >= pd.Timestamp('2025-01-01')
def fila(nom, d_full, d_var):
    x = d_full-d_var; out = [nom]
    for m in (np.ones(len(x), bool), h1, h2, r2526):
        dd = x[m]; t = dd.mean()/dd.std(ddof=1)*np.sqrt(len(dd)) if dd.std() > 0 else 0.0
        out.append(f"{dd.mean():+6.2f} (t {t:+4.1f})")
    return out

if __name__ == '__main__':
    print('días', len(K), '·', fechas[0].date(), '→', fechas[-1].date(), flush=True)
    import pickle
    CB = construir(); pickle.dump(CB, open('rg_base.pkl', 'wb'))
    MO, MR = pesos(); d_full, no, nr = diario(CB, MO, MR)
    print(f"BOT COMPLETO $/día por MNQ base: todo {d_full.mean():.2f} · 1.ª mitad {d_full[h1].mean():.2f} · 2.ª {d_full[h2].mean():.2f} · 2025–26 {d_full[r2526].mean():.2f}", flush=True)
    for e, (C0, C2) in (('ORB', (0, 1)), ('Ruido', (2, 3))):
        z = CB[C0][:, -1] if e == 'ORB' else CB[2][:, -1]
        for nm, m in (('todo', np.ones(len(z), bool)), ('1.ª mitad', h1), ('2.ª mitad', h2), ('2025–26', r2526)):
            zz = z[m]; zz = zz[zz != 0]
            print(f"  {e} sin capas 1 MNQ {nm:9}: ${zz.mean():6.1f}/operación · t {zz.mean()/zz.std()*np.sqrt(len(zz)):+4.1f} · n {len(zz)}", flush=True)
    print('\nregla | efecto de TENERLA en $/día por MNQ base: todo | 1.ª mitad | 2.ª mitad | 2025–26', flush=True)
    V = {}
    for nom, kw in (('BE ORB +$150', dict(be=False)), ('Sacudida ORB 0.6%', dict(sac=False)), ('Sin ORB en día de Fed', dict(fed=False)),
                    ('ORB con órdenes pendientes (vs a mercado)', dict(costo_orb=10)), ('Escalera ruido', dict(esc=False))):
        V[nom] = construir(**kw); d, _, _ = diario(V[nom], MO, MR); print(' | '.join(fila(nom, d_full, d)), flush=True)
    for nom, kw in (('Ruido stop 1% (Neon) vs sin stop', dict(stop_r=0.01)), ('Ruido stop 2.5% vs sin stop', dict(stop_r=0.025))):
        V[nom] = construir(**kw); d, _, _ = diario(V[nom], MO, MR); print(' | '.join(fila(nom, d, d_full)), flush=True)
    for nom, s in (('Tamaño por volatilidad', 'vol'), ('VIX9D/VIX ×0.5', 'r9'), ('Gigantes ×1.5', 'gig'), ('COT ×0.5', 'cot'), ('NFP ruido ×1.5', 'nfp'),
                   ('Filtro de caída', 'caida'), ('Cierre de ayer en su rango', 'pay'), ('Tope 2×', 'tope')):
        mo, mr = pesos((s,)); d, _, _ = diario(CB, mo, mr); print(' | '.join(fila(nom, d_full, d)), flush=True)
    d, _, _ = diario(CB, MO, MR, margen=True); print(' | '.join(fila('Guardia de margen 85% (1:15) vs sin', d, d_full)), flush=True)
    pickle.dump(V, open('rg_var.pkl', 'wb'))
