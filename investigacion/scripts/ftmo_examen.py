import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault('JUEZ_AHORA','2026-11-17T00:00:00')
sys.path.insert(0,'/home/claude/bot-tendencias'); import juez as J
C = pd.read_csv('/home/claude/bot-tendencias/precios.csv', parse_dates=['fecha']).set_index('fecha')
cfg = json.load(open('/home/claude/bot-tendencias/config_tendencia.json'))
v = dict(lookbacks=cfg['lookbacks'], vol_dias=cfg['vol_dias'], **cfg.get('reglas', {}))
mon = ['ETH','SOL','XRP','LTC','ADA','AVAX']
def examen(r, meta, tope=-0.08, diario=-0.05, n=20000, bloque=20, seed=1):
    r=r.dropna().values; rng=np.random.default_rng(seed); ok=[]; dias=[]
    for _ in range(n):
        eq=1.0; d=0; res=None
        while d < 365:
            i=rng.integers(len(r)-bloque)
            for x in r[i:i+bloque]:
                d+=1
                if x <= diario: res=False; break
                eq*=1+x
                if eq-1 <= tope: res=False; break
                if eq-1 >= meta: res=True; break
            if res is not None: break
        ok.append(res is True); dias.append(d)
    ok=np.array(ok); dias=np.array(dias)
    return ok.mean(), np.median(dias[ok]) if ok.any() else None
print('FTMO (fase 1: +10% antes de -8% del bot, sin perder 5% en un día), 6 monedas, reglas actuales:')
for vo in (0.25, 0.40, 0.60, 0.88):
    r = J.correr(C, v, mon, vo).loc['2021-09-01':]
    p, dm = examen(r, 0.10)
    print(f'vol objetivo {vo:.0%}: rendimiento anual {(1+r).prod()**(365/len(r))-1:6.0%} · Sharpe {J.sharpe(r):.2f} · peor día {r.min():.1%} · pasa {p:.0%} · días para pasar (mediana) {dm}')
