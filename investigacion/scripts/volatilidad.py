"""Capa de volatilidad (estudio, sin tocar el bot): variantes vs la actual. $/día, Sharpe por mitades y FTMO (freno + agotado 2%)."""
import pickle, numpy as np, pandas as pd
import reglas as R
exec(open('freno_v3.py').read().split("if __name__")[0])
CB = pickle.load(open('rg_base.pkl', 'rb'))
act = hacer(lambda m: max(400, 60*m), ('reto', 'fond'))
def mitad(C):
    q = 15.0*np.arange(1, 79)/78; return tuple(x-q/2 for x in C)
arr = R.arr; K = list(R.K)
def vol_n(n):
    v = pd.Series([np.mean([arr[j].h.max()-arr[j].l.min() for j in range(k-n, k)])/arr[k-1].c[-1] for k in K], index=R.fechas)
    med = v.rolling(250, min_periods=60).median().fillna(v.expanding().median()); return (med/v).values
raw14 = vol_n(14); W0 = R.W.vol.values
assert np.allclose(np.clip(raw14, 0.5, 1.5), W0, equal_nan=True), 'no reproduce la capa actual'
base_o, base_r = R.pesos(('vol',))      # todo menos volatilidad (sin tope todavía: el tope 2× ya va dentro de pesos)
def con(peso_o, peso_r):
    S = ('vol',)
    vol1 = np.ones(len(K)); r9 = R.W.r9.values; cot = R.W.cot.fillna(1).values
    gig = np.where(R.W.gig.fillna(False).values, 1.5, 1); nfp = np.where(R.W.nfp.fillna(False).values, 1.5, 1)
    co = np.where(R.ret1 < -0.02, 0, 1); cr = np.where(R.ret1 < -0.01, 0, 1)
    py = np.where(R.pay > 0.8, 1.5, np.where(R.pay < 0.2, 0.5, 1))
    return np.minimum(peso_o*r9*cot*gig*co, 2.0), np.minimum(peso_r*r9*cot*gig*nfp*cr*py, 2.0)
sh = lambda d, m: d[m].mean()/d[m].std()*np.sqrt(252)
def corre(nom, po, pr):
    global MO, MR
    MO, MR = con(po, pr); d, _, _ = R.diario(CB, MO, MR)
    out = [f"{nom:30} ${d.mean():5.1f}/día · Sharpe {sh(d, np.ones(len(d),bool)):.2f} ({sh(d,R.h1):.2f}/{sh(d,R.h2):.2f}/{sh(d,R.r2526):.2f})"]
    for Cx in (CB, mitad(CB)):
        A = np.array([dos_pasos3(s, Cx, 4, act, 2000) for s in starts]); g = A[:, 0]
        out.append(f"{np.mean(A[:,1]==0):3.0%} ${np.median(g)/1e3:4.1f}k")
    print(' · '.join(out), flush=True)
print('variante | $/día · Sharpe todo (1.ª/2.ª mitad/2025–26) · FTMO no cobra y mediana (pruebas · mitad), agotado 2%')
one = np.ones(len(K)); c = lambda x, a, b: np.clip(x, a, b)
corre('ACTUAL 14 d, 0.5–1.5', W0, W0)
corre('sin capa', one, one)
corre('rango 0.75–1.25', c(raw14,.75,1.25), c(raw14,.75,1.25))
corre('solo recorta 0.5–1.0', c(raw14,.5,1), c(raw14,.5,1))
corre('solo agranda 1.0–1.5', c(raw14,1,1.5), c(raw14,1,1.5))
corre('suavizada √, 0.5–1.5', c(np.sqrt(raw14),.5,1.5), c(np.sqrt(raw14),.5,1.5))
corre('solo en el ORB', W0, one)
corre('solo en el ruido', one, W0)
for n in (5, 30):
    v = c(vol_n(n), .5, 1.5); corre(f'ventana {n} días, 0.5–1.5', v, v)
