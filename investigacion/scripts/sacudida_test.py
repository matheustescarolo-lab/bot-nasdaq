"""Test directo de la sacudida 0.6% (sin buscar parámetros): ORB del bot (BE $150, sin ORB en Fed) con y sin sacudida,
1 MNQ, costo 1.5 pts. Solo los días en que la sacudida se dispara cambian; ahí se compara el resultado real vs el contrafactual."""
import sys, numpy as np, pandas as pd
sys.argv = ['x']; exec(open('sobreajuste.py').read().split('def dia(')[0])    # trae R, arr, K, orb_p, pnl
f = pd.to_datetime([pd.Timestamp(arr[k].d) for k in K])
con, sin, px, hora = [], [], [], []
for k in K:
    g = arr[k]
    if pd.Timestamp(g.d) in R.FOMC: con.append(0); sin.append(0); px.append(g.o[0]); hora.append(-1); continue
    a, b = orb_p(g, 150, 0.006), orb_p(g, 150, None)
    con.append(pnl(a, 3)); sin.append(pnl(b, 3)); px.append(g.o[0])
    hora.append(a[0][4] if a and a != b else -1)
con, sin, px, hora = map(np.array, (con, sin, px, hora))
d = con - sin; m = d != 0; bps = d / (px * 2) * 1e4           # efecto en bps del precio (el índice valía 3.6× menos en 2019)
t = lambda x: x.mean()/x.std(ddof=1)*np.sqrt(len(x))
print(f"Días con sacudida que cambia el resultado: {m.sum()} de {len(K)} ({m.mean():.1%}) · ~{m.sum()/7.8:.0f} al año")
print(f"En esos días: con sacudida ${con[m].mean():.0f}/trade · sin sacudida ${sin[m].mean():.0f} · efecto ${d[m].mean():+.0f}/trade")
print(f"  la sacudida ayudó {np.mean(d[m] > 0):.0%} de las veces · ganancia media cuando ayuda ${d[m][d[m] > 0].mean():.0f} · costo medio cuando estorba ${d[m][d[m] < 0].mean():.0f}")
print(f"Efecto total: ${d.sum():+,.0f} en 8 años · ${d.mean():+.2f}/día (t {t(d):+.2f}) · en bps/día {bps.mean():+.3f} (t {t(bps):+.2f})")
print(f"Peor día evitado ${d.max():,.0f} · peor día causado ${d.min():,.0f}")
for nom, s in (('2019–22', f.year < 2023), ('2023–26', f.year >= 2023)):
    print(f"  {nom}: ${d[s].mean():+.2f}/día (t {t(d[s]):+.2f}) · bps t {t(bps[s]):+.2f} · disparos {m[s].sum()} · ayudó {np.mean(d[s & m] > 0):.0%}")
print('  por año ($ total):', ' · '.join(f"{y}: {d[f.year == y].sum():+,.0f} ({m[f.year == y].sum()})" for y in range(2019, 2027)))
for nom, x in (('con sacudida', con), ('sin sacudida', sin)):
    eq = np.cumsum(x); dd = (eq - np.maximum.accumulate(eq)).min(); s = x[x != 0]
    print(f"  ORB {nom}: ${x.mean():.2f}/día · Sharpe {x.mean()/x.std()*np.sqrt(252):.2f} · peor día ${x.min():,.0f} · máx. caída ${dd:,.0f} · días < −$600: {(x < -600).sum()}")
v = np.array([np.abs(arr[k].c[-1]/arr[k].o[0]-1) for k in K]); alta = v > np.median(v)
print(f"  volatilidad del día alta: efecto ${d[alta].mean():+.2f}/día (t {t(d[alta]):+.2f}) · baja ${d[~alta].mean():+.2f} (t {t(d[~alta]):+.2f})")
print(f"  disparo antes de 11:00 NY: ${d[(hora >= 0) & (hora < 18)].mean() * 0 + d[(hora >= 0) & (hora < 18)].sum()/len(K):+.2f}/día · después: ${d[hora >= 18].sum()/len(K):+.2f}/día")
