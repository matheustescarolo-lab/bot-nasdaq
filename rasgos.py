"""
Rasgos del modelo con contexto. El MISMO código se usa para entrenar (historia de Dukascopy) y en vivo (bot), para que
el modelo vea exactamente lo mismo en los dos lados. Sin ver el futuro: en el rango de 30 min se usa el precio de entrada
y el VWAP hasta la vela anterior; en la zona de ruido, el cierre de la vela del chequeo (la entrada ocurre a ese cierre).
"""
import json, math
import numpy as np
import pandas as pd

FE = ['vix', 'vix_rel', 'vix_5d', 'spx_tend', 'noc_rango', 'noc_pos', 'al_noc_pos', 'al_noc_ult3h', 'al_spx_1d',
      'al_usd_5d', 'al_bono_5d', 'nominas', 'opex', 'fin_mes', 'gap', 'ret1', 'ret5', 'tend20', 'vol14', 'rvol', 'ancho',
      'or_ret', 'pos_ayer', 'lado', 'n_previas', 'minuto', 'al_tend', 'al_gap', 'al_or', 'dist_vwap', 'mov_previo']


def _a(d, k):
    return np.asarray(d[k] if isinstance(d, (pd.DataFrame, dict)) else getattr(d, k), dtype=float)


def base_dia(previos, hoy):
    """previos: últimos ≥20 días completos (horario normal, velas de 5 min) del más viejo al más nuevo; hoy: velas de hoy (≥6)."""
    p = previos[-1]; pc = _a(p, 'c')[-1]
    cierres = np.array([_a(d, 'c')[-1] for d in previos[-20:]])
    rango_med = np.mean([_a(d, 'h').max() - _a(d, 'l').min() for d in previos[-14:]])
    vol30m = np.mean([_a(d, 'v')[:6].sum() for d in previos[-14:]])
    o, h, l, c, v = (_a(hoy, k) for k in 'ohlcv')
    return dict(gap=o[0] / pc - 1, ret1=pc / _a(previos[-2], 'c')[-1] - 1, ret5=pc / _a(previos[-6], 'c')[-1] - 1,
                tend20=pc / cierres.mean() - 1, vol14=rango_med / pc, rvol=v[:6].sum() / max(vol30m, 1),
                ancho=(h[:6].max() - l[:6].min()) / rango_med, or_ret=c[5] / o[0] - 1,
                pos_ayer=(pc - _a(p, 'l').min()) / max(_a(p, 'h').max() - _a(p, 'l').min(), 1e-9))


def ctx_series(d1, vix):
    """d1: DataFrame (índice = fecha UTC de la vela diaria de Dukascopy) con columnas spx, usd, bono (cierres);
    vix: Serie diaria (Yahoo ^VIX). Devuelve los indicadores diarios por fecha (todavía sin desplazar)."""
    ctx = d1[['spx', 'usd', 'bono']].copy()
    ctx['vix'] = vix.reindex(ctx.index.union(vix.index)).ffill().reindex(ctx.index)
    ctx = ctx.ffill()
    F = pd.DataFrame(index=ctx.index)
    F['vix'] = ctx.vix; F['vix_rel'] = ctx.vix / ctx.vix.rolling(20).mean() - 1; F['vix_5d'] = ctx.vix.pct_change(5)
    F['spx_1d'] = ctx.spx.pct_change(); F['spx_tend'] = ctx.spx / ctx.spx.rolling(50).mean() - 1
    F['usd_5d'] = ctx.usd.pct_change(5); F['bono_5d'] = ctx.bono.pct_change(5)
    return F


def ctx_dia(F, h1, fecha):
    """Contexto conocido antes de abrir `fecha`: indicadores del último día con fecha < hoy, sesión nocturna
    (velas de 1 h con hora de apertura NY entre las 16:00 de ayer y antes de las 9:00 de hoy) y calendario."""
    fecha = pd.Timestamp(fecha).normalize()
    prev = F[F.index < fecha]
    if len(prev) == 0:
        return None
    r = prev.iloc[-1].to_dict()
    w = h1[(h1.index >= fecha - pd.Timedelta(hours=8)) & (h1.index < fecha + pd.Timedelta(hours=9))]
    if len(w) < 8:
        return None
    rng = w.high.max() - w.low.min(); ult = w.close.iloc[-1]
    r.update(noc_rango=rng / ult, noc_pos=(ult - w.low.min()) / max(rng, 1e-9), noc_ult3h=ult / w.close.iloc[-4] - 1)
    r.update(nominas=int(fecha.dayofweek == 4 and fecha.day <= 7), opex=int(fecha.dayofweek == 4 and 15 <= fecha.day <= 21),
             fin_mes=int((fecha + pd.offsets.BDay(1)).month != fecha.month))
    return {k: (None if (isinstance(x, float) and math.isnan(x)) else float(x)) for k, x in r.items()}


def rasgos_trade(base, ctx, estr, lado, n_previas, a, e, hoy):
    """a = índice de la vela de entrada de hoy; e = precio de entrada."""
    o, h, l, c, v = (_a(hoy, k) for k in 'ohlcv')
    vw = np.cumsum((h + l + c) / 3 * v) / np.maximum(np.cumsum(v), 1)
    if estr == 'orb':
        ref_vw, ref_px = vw[a - 1], e                      # entra dentro de la vela a: solo se conoce hasta la vela anterior
    else:
        ref_vw, ref_px = vw[a], c[a]                       # entra al cierre de la vela a
    f = dict(base); f.update(ctx)
    s = lado
    f.update(lado=s, n_previas=n_previas, minuto=a * 5 + 5, al_tend=s * np.sign(f['tend20']), al_gap=s * np.sign(f['gap']),
             al_or=s * np.sign(f['or_ret']), dist_vwap=s * (ref_px - ref_vw) / ref_px, mov_previo=s * (ref_px / o[0] - 1))
    for k in ('vix_5d', 'spx_1d', 'spx_tend', 'usd_5d', 'bono_5d', 'noc_ult3h'):
        f['al_' + k] = s * np.sign(f[k]) if f.get(k) is not None else 0.0
    f['al_noc_pos'] = s * (f['noc_pos'] - 0.5)
    return {k: float(f[k]) if f.get(k) is not None else 0.0 for k in FE}


def probabilidad(modelo, estr, f):
    m = modelo[estr]
    x = (np.array([f[k] for k in modelo['rasgos']]) - np.array(m['media'])) / np.array(m['escala'])
    z = float(np.dot(x, m['coef']) + m['intercepto'])
    return 1 / (1 + math.exp(-z))


def cargar_modelo(ruta):
    with open(ruta, encoding='utf-8') as fh:
        return json.load(fh)
