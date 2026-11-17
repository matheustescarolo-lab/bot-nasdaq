"""
Reglas de las dos estrategias, sin nada de MetaTrader (se pueden probar en cualquier compu).
Son las mismas del indicador «MNQ señales» y del juez diario (mnq_diario.py):
  - ORB30: rango de los primeros 30 min (9:30–10:00 Nueva York). La primera ruptura después de las 10:00 entra;
    stop en el otro lado del rango; si una vela rompe los dos lados, ese día no opera. Sin objetivo: cierra al final del día.
  - Zona de ruido (Zarattini, Aziz y Barbon 2024): a las :00 y :30 (desde las 10:00) compra si cierra arriba de la zona,
    vende si cierra abajo; sale cuando cierra del otro lado de max(zona, VWAP) / min(zona, VWAP).
Cada día es un DataFrame de velas de 5 min (hora de Nueva York) con columnas o, h, l, c, v; índice = hora de apertura de la vela.
"""
import datetime as dt
import numpy as np

LOOK = 14                 # días para la zona de ruido
VELAS_DIA_MIN = 70        # un día cuenta como completo con al menos 70 de sus 78 velas (igual que el juez)
T = lambda hhmm: dt.time(int(hhmm[:2]), int(hhmm[3:]))


def niveles_orb(hoy):
    """Alto y bajo de las 6 velas de 9:30 a 9:55. None si faltan velas."""
    r = hoy[(hoy.index.time >= T('09:30')) & (hoy.index.time < T('10:00'))]
    if len(r) < 6:
        return None
    return float(r.h.max()), float(r.l.min())


def modelo_orb(hoy, hi, lo):
    """Qué diría el modelo con las velas de hoy (incluida la que se está formando).
    Devuelve (lado, estado): lado 1 compra / -1 venta / 0 nada; estado 'esperando', 'activo', 'stop' o 'ambos'."""
    d = hoy[hoy.index.time >= T('10:00')]
    for k in range(len(d)):
        up, dn = d.h.iloc[k] > hi, d.l.iloc[k] < lo
        if up and dn:
            return 0, 'ambos'
        if up or dn:
            s = 1 if up else -1
            st = lo if up else hi
            if (s == 1 and d.c.iloc[k] <= st) or (s == -1 and d.c.iloc[k] >= st):
                return s, 'stop'
            for j in range(k + 1, len(d)):
                if (s == 1 and d.l.iloc[j] <= st) or (s == -1 and d.h.iloc[j] >= st):
                    return s, 'stop'
            return s, 'activo'
    return 0, 'esperando'


def movimientos(dia):
    """|cierre / apertura del día - 1| en cada vela del día."""
    return np.abs(dia.c.values / dia.o.values[0] - 1)


def sigma(hist, i):
    """Promedio del movimiento en la vela i de los días de 'hist' (si un día es más corto, usa su último valor)."""
    return float(np.mean([m[i] if len(m) > i else m[-1] for m in hist]))


def chequeos_ruido(hoy, ahora_ny):
    """Velas de hoy que ya cerraron a las :00 o :30 (desde las 10:00 y antes del cierre de las 16:00)."""
    out = []
    for i, t in enumerate(hoy.index):
        fin = t + dt.timedelta(minutes=5)
        if fin > ahora_ny:
            break
        if fin.minute in (0, 30) and fin.time() >= T('10:00') and fin.time() < T('16:00'):
            out.append(i)
    return out


def modelo_ruido(hoy, previos, cierre_ayer, ahora_ny):
    """Repite todos los chequeos de hoy hasta ahora y dice en qué posición debería estar el modelo.
    previos = lista de los últimos LOOK días completos (DataFrames).
    Devuelve (posición, detalle del último chequeo, hora del último chequeo) o (None, motivo, None)."""
    if len(previos) < LOOK or cierre_ayer is None or len(hoy) == 0:
        return None, f'faltan días de historia ({len(previos)} de {LOOK})', None
    hist = [movimientos(d) for d in previos[-LOOK:]]
    op = float(hoy.o.iloc[0])
    tp = (hoy.h + hoy.l + hoy.c) / 3
    vw = np.cumsum(tp.values * hoy.v.values) / np.maximum(np.cumsum(hoy.v.values), 1)
    pos, info, ultimo = 0, '', None
    for i in chequeos_ruido(hoy, ahora_ny):
        sg = sigma(hist, i)
        ub, lb = max(op, cierre_ayer) * (1 + sg), min(op, cierre_ayer) * (1 - sg)
        c = float(hoy.c.iloc[i])
        if pos == 1 and c < max(ub, vw[i]):
            pos = 0
        elif pos == -1 and c > min(lb, vw[i]):
            pos = 0
        if pos == 0:
            pos = 1 if c > ub else -1 if c < lb else 0
        fin = (hoy.index[i] + dt.timedelta(minutes=5)).strftime('%H:%M')
        info = f'chequeo {fin} NY: cierre {c:,.2f} · zona {lb:,.2f}–{ub:,.2f} · VWAP {vw[i]:,.2f}'
        ultimo = hoy.index[i] + dt.timedelta(minutes=5)
    return pos, info, ultimo
