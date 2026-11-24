import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
T=pd.read_pickle('trades8.pkl')
X=['gap','ret1','ret5','tend20','vol14','rvol','ancho','or_ret','pos_ayer','lado','n_previas','minuto','al_tend','al_gap','al_or','dist_vwap','mov_previo']
def evalua(estr, modelo):
    D=T[T.estr==estr].copy(); out=[]
    for y in range(2021, 2027):
        tr, te = D[D.año<y], D[D.año==y]
        m = modelo(); m.fit(tr[X], tr.gana)
        p = m.predict_proba(te[X])[:,1]
        corte = np.quantile(m.predict_proba(tr[X])[:,1], 0.4)     # salta el 40% de trades con peor pronóstico (según el entrenamiento)
        te = te.assign(p=p, toma=p>corte); out.append(te)
    R=pd.concat(out)
    print(f'\n{estr.upper()} — {modelo.__name__}')
    print(f"{'año':>5} | {'base: trades, aciertos, US$':>30} | {'con modelo: trades, aciertos, US$':>34}")
    for y,g in R.groupby('año'):
        t=g[g.toma]
        print(f"{y:>5} | {len(g):>6} {g.gana.mean():6.0%} {g.pnl.sum():>9,.0f}      | {len(t):>6} {t.gana.mean():6.0%} {t.pnl.sum():>9,.0f}")
    t=R[R.toma]
    print(f"TOTAL | {len(R):>6} {R.gana.mean():6.0%} {R.pnl.sum():>9,.0f}      | {len(t):>6} {t.gana.mean():6.0%} {t.pnl.sum():>9,.0f}  · por trade ${R.pnl.mean():.1f} → ${t.pnl.mean():.1f}")
    return R
log = lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000))
log.__name__='regresión logística'
gb = lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40)
gb.__name__='árboles (gradient boosting)'
for e in ('orb','ruido'):
    for m in (log, gb): evalua(e, m)
