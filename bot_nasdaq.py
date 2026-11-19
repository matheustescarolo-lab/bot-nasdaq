"""
BOT NASDAQ (demo) — opera en MT5 de Tickmill el CFD del Nasdaq-100 (USTEC) con las dos estrategias de la prueba MNQ:
rango de 30 min (ORB30) y zona de ruido. Tamaño: lo equivalente a 1 MNQ por estrategia (US$2 por punto = 2 lotes de USTEC).
Corre en GitHub Actions en dos tramos al día (los lanza cron-job.org):
  - mañana: de ~9:45 a 12:50 de Nueva York   - tarde: de ~12:45 a 15:58 de Nueva York (cierra todo a las 15:55)
Cada tramo vuelve a calcular lo que diría el modelo con las velas de hoy y deja la cuenta igual que el modelo, así que
si un tramo arranca tarde o se cae, el siguiente se pone al día solo.
Solo opera en cuentas DEMO. Bitácora: bitacora_nasdaq.csv. Al final del día publica el resumen en el issue
«📊 Update diario del bot Nasdaq» (GitHub te avisa por correo).
Conexión: variables MT5_LOGIN, MT5_PASSWORD, MT5_SERVER y MT5_PATH.
"""
import os, sys, csv, json, time, datetime as dt, urllib.request
from zoneinfo import ZoneInfo
import pandas as pd
import MetaTrader5 as mt5
from estrategias import niveles_orb, modelo_orb, modelo_ruido, piso_usd, LOOK, VELAS_DIA_MIN, T

HERE = os.path.dirname(os.path.abspath(__file__))
NY, UTC = ZoneInfo('America/New_York'), dt.timezone.utc
SIMBOLOS = ['USTEC', 'US100.cash', 'NAS100', 'US100', 'USTECH', 'NDX100']
# Cuenta: 'tickmill' (demo, 3 versiones del examen de Lucid) o 'ftmo' (reto FTMO 2-Step real: metas 10% y 5%, pérdida diaria 5%, máxima 10% fija)
CUENTA = os.environ.get('BOT_CUENTA', 'tickmill').lower()
SUF = '' if CUENTA == 'tickmill' else f'_{CUENTA}'
MODO = (os.environ.get('BOT_MODO') or ('ftmo' if CUENTA == 'ftmo' else 'lucid')).lower()   # reglas que sigue: ftmo | lucid (independiente de la cuenta)
BITACORA = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'bitacora_nasdaq{SUF}.csv')
FTMO_INICIAL = float(os.environ.get('BOT_FTMO_INICIAL', '100000'))   # capital inicial de la cuenta FTMO
ETAPA = os.environ.get('BOT_FTMO_ETAPA', 'reto')   # reto (fase 1 y 2 simuladas en la misma cuenta) | fase1 | fase2 | fondeada
TOPE_FTMO = 2.0      # máximo 2× la base por estrategia en FTMO (8 años: −5–8% de profit, misma probabilidad de cobrar)
FTMO_FRENO = 0.004              # cierra todo al quedar a 0.4% del capital de los límites de FTMO (tocarlos = cuenta perdida)
DOLARES_POR_PUNTO = 2.0          # 1 MNQ = US$2 por punto del Nasdaq-100
# ===== Modo examen (desde el 18-nov-2026): agresivo pero con reglas, simulando el examen de Lucid Flex 50K =====
CONTRATOS = int(os.environ.get('BOT_MNQ', '4'))                 # MNQ por estrategia que opera la demo (= versión B)
# 3 versiones del examen en paralelo con los mismos trades (escaladas): A 3 MNQ, B 4 MNQ, C 6 MNQ. La demo opera B y solo cierra
# todo cuando las 3 terminaron su día (meta o quemado). Simulación 8 años: B la más robusta; ver claude/mnq-lucid.md.
VERSIONES = {'A': 3, 'B': 4, 'C': 6}
META_DIARIA = float(os.environ.get('BOT_META_DIARIA', '1550'))   # al ganar esto en el día, cierra todo y para hasta mañana
EXAMEN_META, EXAMEN_MLL, EXAMEN_BLOQUEO = 3000.0, 2000.0, 2100.0  # reglas de Lucid Flex 50K
ESTADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'estado_nasdaq{SUF}.json')
MAGIC = {'orb': 301, 'ruido': 302}
NOMBRE = {'orb': 'Rango 30 min', 'ruido': 'Zona de ruido'}
STOP_EMERGENCIA = 0.025          # zona de ruido: stop en el servidor a 2.5% en contra (por si el bot se cae con la posición abierta)
CIERRE = T('15:55')
FIN_MANANA = T('12:50')
FERIADOS = {'2026-11-26', '2026-12-25', '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31',
            '2027-06-18', '2027-07-05', '2027-09-06', '2027-11-25', '2027-12-24'}
# Días de decisión de la Fed (2 pm NY): el rango de 30 min gana solo 20% de las veces (−US$35/trade, t = −3.0 en 8 años) → ese día no opera ORB
# Fuente: federalreserve.gov, comunicado del 12-nov-2026 (calendario tentativo revisado de 2027; octubre 26-27 sin decisión,
# noviembre reemplaza a diciembre). Revisar si la Fed mueve alguna fecha.
FOMC = {'2026-12-09', '2027-01-27', '2027-03-17', '2027-04-28', '2027-06-09', '2027-07-28', '2027-09-15', '2027-11-17'}
MEDIO_DIA = {'2026-11-27', '2026-12-24', '2027-11-26'}        # la bolsa cierra a las 13:00: el bot cierra todo a las 12:55
FILL = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
DESFASE = None
CONTEXTO = {}                   # segundos que hay que restar a la hora del servidor para tener la de Nueva York


def ahora_ny():
    return dt.datetime.now(NY).replace(tzinfo=None)


def log(evento, estrategia='', lado='', lotes='', precio='', detalle=''):
    f = BITACORA; nuevo = not os.path.exists(f)
    fila = [dt.datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S'), evento, estrategia, lado, lotes, precio, detalle]
    with open(f, 'a', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if nuevo:
            w.writerow(['hora_UTC', 'evento', 'estrategia', 'lado', 'lotes', 'precio', 'detalle'])
        w.writerow(fila)
    print(' | '.join(str(x) for x in fila if x != ''), flush=True)


# ===== MT5 =====
def iniciar():
    login, ruta = os.environ.get('MT5_LOGIN', '').strip(), os.environ.get('MT5_PATH', '').strip()
    kw = dict(login=int(login), password=os.environ.get('MT5_PASSWORD', ''), server=os.environ.get('MT5_SERVER', '').strip(),
              timeout=180000) if login else {}
    return mt5.initialize(ruta, **kw) if ruta else mt5.initialize(**kw)


def conectado():
    if mt5.account_info() is not None:
        return True
    for _ in range(3):
        mt5.shutdown(); time.sleep(3)
        if iniciar() and mt5.account_info() is not None:
            log('reconexion', detalle='MT5 se había desconectado; reconectado')
            return True
    return False


def buscar_simbolo():
    for n in SIMBOLOS:
        if mt5.symbol_info(n) is not None and mt5.symbol_select(n, True):
            return n
    return None


def calcular_desfase(sym):
    """La hora del servidor de Tickmill va 7 h adelante de Nueva York todo el año; se comprueba con el último precio."""
    global DESFASE
    t = mt5.symbol_info_tick(sym)
    srv_menos_utc = round((t.time - time.time()) / 1800) * 1800 if t and t.time else None
    ny_menos_utc = int(dt.datetime.now(NY).utcoffset().total_seconds())
    DESFASE = 7 * 3600
    if srv_menos_utc is not None and srv_menos_utc - ny_menos_utc != DESFASE:
        DESFASE = srv_menos_utc - ny_menos_utc
        log('aviso', detalle=f'el servidor no va 7 h adelante de Nueva York: uso {DESFASE / 3600:+.1f} h')


def a_ny(t_servidor):
    return dt.datetime(1970, 1, 1) + dt.timedelta(seconds=int(t_servidor) - DESFASE)


def velas(sym):
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 9000)
    if r is None or len(r) == 0:
        return None
    df = pd.DataFrame(r)
    df.index = [a_ny(x) for x in df['time']]
    df = df.rename(columns={'open': 'o', 'high': 'h', 'low': 'l', 'close': 'c', 'tick_volume': 'v'})[['o', 'h', 'l', 'c', 'v']]
    return df[(df.index.time >= T('09:30')) & (df.index.time < T('16:00'))]


def partir_dias(df, hoy):
    dias = {d: g for d, g in df.groupby(df.index.date)}
    previos = [g for d, g in sorted(dias.items()) if d < hoy and str(d) not in FERIADOS and len(g) >= VELAS_DIA_MIN]
    return dias.get(hoy, df.iloc[0:0]), previos


def contratos_hoy(sym):
    """Tamaño según la volatilidad (8 años: Sharpe 1.38→1.45, peor caída −19%): más MNQ en días tranquilos, menos en agitados.
    Igual que la simulación: volatilidad = promedio de (máximo − mínimo) del horario normal (9:30–16:00) de los últimos 14 días
    / cierre de ayer; peso = mediana de esa volatilidad en el último año / la de hoy, entre 0.5× y 1.5× de CONTRATOS.
    Usa velas de 30 min (cubren ~1 año); si no alcanzan, velas diarias de 24 h (aproximación)."""
    try:
        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M30, 0, 20000)
        d = pd.DataFrame(r)
        d.index = [a_ny(x) for x in d['time']]
        d = d[(d.index.time >= T('09:30')) & (d.index.time < T('16:00'))]
        hoy_ny = ahora_ny().date()
        g = d.groupby(d.index.date).agg(h=('high', 'max'), l=('low', 'min'), c=('close', 'last'), n=('close', 'size'))
        g = g[(g.n >= 12) & (g.index < hoy_ny) & ~pd.Index([str(x) for x in g.index]).isin(list(FERIADOS))]
        if len(g) < 80:
            raise ValueError(f'solo {len(g)} días en velas de 30 min')
        v = (g.h - g.l).rolling(14).mean() / g.c
        hoy, med, fuente = float(v.iloc[-1]), float(v.iloc[-250:].median()), 'horario normal'
    except Exception as e1:
        try:
            r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 1, 300)          # desde ayer hacia atrás
            d = pd.DataFrame(r)
            v = ((d['high'] - d['low']) / d['close'].shift(1)).rolling(14).mean()
            hoy, med, fuente = float(v.iloc[-1]), float(v.iloc[-250:].median()), f'velas diarias 24 h ({e1})'
        except Exception as e:
            log('aviso', detalle=f'no pude calcular la volatilidad ({e}); uso {CONTRATOS} MNQ')
            return CONTRATOS, 1.0, None, None
    peso = min(1.5, max(0.5, med / hoy))
    if fuente != 'horario normal':
        log('aviso', detalle=f'volatilidad calculada con {fuente}'[:200])
    return max(1, round(CONTRATOS * peso)), peso, hoy, med


def leer_contexto(hoy):
    """Contexto del día bajado por contexto.py (calendario, reportes, futuros, VIX). {} si no hay o es de otro día."""
    try:
        with open(os.path.join(HERE, 'contexto', 'hoy.json'), encoding='utf-8') as fh:
            c = json.load(fh)
        return c if c.get('fecha') == str(hoy) else {}
    except Exception:
        return {}


def factor_evento():
    """Ajustes de tamaño por eventos del contexto: (factor para las dos estrategias, ¿es día de NFP?, motivos)."""
    if not CONTEXTO:
        return 1.0, False, []
    m = CONTEXTO.get('marcas') or {}
    f, mot = 1.0, []
    ayer = [r['simbolo'] for r in (CONTEXTO.get('reportes_ayer') or []) if 'pre' not in (r.get('hora') or '').lower() and r.get('simbolo') != 'ASML']   # ASML cuenta el mismo día (igual que la simulación)
    hoy_antes = [r['simbolo'] for r in (CONTEXTO.get('reportes_hoy') or []) if 'pre' in (r.get('hora') or '').lower() or r.get('simbolo') == 'ASML']
    if ayer or hoy_antes:
        f *= EVENTO_GIGANTES; mot.append(f"reporte de gigantes ({', '.join(ayer + hoy_antes)})")
    if m.get('fondos_semana') == 'recortaron fuerte':
        f *= COT_RECORTE; mot.append('fondos apalancados recortaron fuerte (COT)')
    return f, bool(m.get('empleo_nfp')), mot


def leer_estado():
    try:
        with open(ESTADO, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def guardar_estado(e):
    with open(ESTADO, 'w', encoding='utf-8') as fh:
        json.dump(e, fh, ensure_ascii=False, indent=1)


def examen_nuevo(e, v, hoy, n_prev=0):
    e.setdefault('versiones', {})[v] = dict(n=n_prev + 1, inicio=str(hoy), saldo=0.0, alto=0.0, mll=-EXAMEN_MLL, bloq=False, mejor_dia=0.0, dias=0)


def meta_del_dia(bal):
    """Meta del día = lo justo que falta para +3,000, sin que el día pase de 50% (consistencia) y con tope META_DIARIA.
    8 años: pasa 22%→25% por intento (en las dos mitades), misma velocidad."""
    if not META_DIARIA:
        return 0
    falta = EXAMEN_META - bal
    if bal > 0 and falta + 50 <= bal:
        meta = min(META_DIARIA, falta + 50)
    elif bal > 0:
        meta = min(META_DIARIA, bal)
    else:
        meta = META_DIARIA
    return max(meta, 300.0)


def lotes_por_mnq(info):
    usd_por_punto_lote = info.trade_tick_value / info.trade_tick_size if info.trade_tick_size else 1.0
    paso = info.volume_step or 0.01
    return max(info.volume_min, round(round(DOLARES_POR_PUNTO / usd_por_punto_lote / paso) * paso, 8))


def posicion(sym, clave):
    ps = [p for p in (mt5.positions_get(symbol=sym) or []) if p.magic == MAGIC[clave]]
    lado = 0 if not ps else (1 if ps[0].type == mt5.POSITION_TYPE_BUY else -1)
    return lado, ps


def opero_hoy(clave, hoy):
    """¿Ya hubo alguna entrada de esta estrategia hoy? (para no volver a entrar en el rango de 30 min después de un stop)."""
    desde = dt.datetime.now(UTC) - dt.timedelta(days=2)
    ds = mt5.history_deals_get(desde, dt.datetime.now(UTC) + dt.timedelta(days=1)) or []
    return any(d.magic == MAGIC[clave] and d.entry == mt5.DEAL_ENTRY_IN and a_ny(d.time).date() == hoy for d in ds)


def salio_por_stop(clave, desde_ny):
    """¿El servidor cerró esta estrategia por stop después del último chequeo?"""
    if desde_ny is None:
        return False
    ds = mt5.history_deals_get(dt.datetime.now(UTC) - dt.timedelta(days=2), dt.datetime.now(UTC) + dt.timedelta(days=1)) or []
    return any(d.magic == MAGIC[clave] and d.entry == mt5.DEAL_ENTRY_OUT and d.reason == mt5.DEAL_REASON_SL
               and a_ny(d.time) >= desde_ny for d in ds)


def enviar(sym, lado, lotes, clave, ticket=None, sl=None):
    t, info = mt5.symbol_info_tick(sym), mt5.symbol_info(sym)
    if t is None or info is None or t.bid <= 0:
        log('error', NOMBRE[clave], detalle=f'sin precio ({mt5.last_error()})'); return None
    precio = t.ask if lado > 0 else t.bid
    req = dict(action=mt5.TRADE_ACTION_DEAL, symbol=sym, volume=float(lotes), price=precio, magic=MAGIC[clave],
               type=mt5.ORDER_TYPE_BUY if lado > 0 else mt5.ORDER_TYPE_SELL, deviation=max(20, int(precio * 0.001 / info.point)),
               comment=clave, type_time=mt5.ORDER_TIME_GTC)
    if ticket is not None:
        req['position'] = ticket
    elif sl is not None:
        minimo = (info.trade_stops_level or 0) * info.point
        if (lado > 0 and sl < precio - minimo) or (lado < 0 and sl > precio + minimo):
            req['sl'] = round(sl, info.digits)
    r = None
    for f in FILL:
        r = mt5.order_send({**req, 'type_filling': f})
        if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
            return r.price or precio
        if r is None or r.retcode != 10030:
            break
    log('error', NOMBRE[clave], 'compra' if lado > 0 else 'venta', lotes,
        detalle=f"orden rechazada: {r.retcode if r else mt5.last_error()} {r.comment if r else ''}")
    return None


def pendientes(sym, clave):
    return [o for o in (mt5.orders_get(symbol=sym) or []) if o.magic == MAGIC[clave]]


def cancelar_pendientes(sym, clave, motivo):
    for o in pendientes(sym, clave):
        r = mt5.order_send(dict(action=mt5.TRADE_ACTION_REMOVE, order=o.ticket))
        if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
            log('cancela', NOMBRE[clave], 'compra' if o.type == mt5.ORDER_TYPE_BUY_STOP else 'venta', o.volume_current,
                f'{o.price_open:.2f}', f'orden pendiente cancelada: {motivo}')
        else:
            log('error', NOMBRE[clave], detalle=f"no pude cancelar la pendiente {o.ticket}: {r.retcode if r else mt5.last_error()}")


def poner_pendiente(sym, clave, lado, lotes, precio, sl, motivo):
    """Orden stop en el servidor: se llena en cuanto el precio toca el nivel (sin esperar al ciclo de 10 s del bot)."""
    info = mt5.symbol_info(sym)
    req = dict(action=mt5.TRADE_ACTION_PENDING, symbol=sym, volume=float(lotes), price=round(precio, info.digits),
               sl=round(sl, info.digits), magic=MAGIC[clave], comment=clave,
               type=mt5.ORDER_TYPE_BUY_STOP if lado > 0 else mt5.ORDER_TYPE_SELL_STOP)
    r = None
    for tt in (mt5.ORDER_TIME_DAY, mt5.ORDER_TIME_GTC):
        for f in (mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK):
            r = mt5.order_send({**req, 'type_time': tt, 'type_filling': f})
            if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
                log('pendiente', NOMBRE[clave], 'compra' if lado > 0 else 'venta', lotes, f'{precio:.2f}', f'{motivo} · stop {sl:,.2f}')
                return True
    log('error', NOMBRE[clave], detalle=f"no pude poner la orden pendiente: {r.retcode if r else mt5.last_error()} {r.comment if r else ''}")
    return False


def entrada_anotada(clave, hoy):
    try:
        with open(BITACORA, encoding='utf-8') as fh:
            return any(f['evento'] == 'entrada' and f['estrategia'] == NOMBRE[clave] and f['hora_UTC'][:10] == f'{hoy:%Y-%m-%d}'
                       for f in csv.DictReader(fh))
    except Exception:
        return False


def cerrar(sym, clave, motivo):
    cancelar_pendientes(sym, clave, motivo)
    _, ps = posicion(sym, clave)
    for p in ps:
        lado = -1 if p.type == mt5.POSITION_TYPE_BUY else 1
        px = enviar(sym, lado, p.volume, clave, ticket=p.ticket)
        if px is not None:
            res = (px - p.price_open) * (-lado) * p.volume * (mt5.symbol_info(sym).trade_tick_value / mt5.symbol_info(sym).trade_tick_size)
            log('salida', NOMBRE[clave], 'venta' if lado < 0 else 'compra', p.volume, f'{px:.2f}',
                f'{motivo} · entró a {p.price_open:.2f} · resultado aprox. {res:+,.2f} USD')


def abrir(sym, clave, lado, lotes, sl, motivo):
    px = enviar(sym, lado, lotes, clave, sl=sl)
    if px is not None:
        log('entrada', NOMBRE[clave], 'compra' if lado > 0 else 'venta', lotes, f'{px:.2f}',
            motivo + (f' · stop {sl:,.2f}' if sl else ''))


# ===== Lógica del día =====
def caida_ayer(previos):
    """Retorno cierre a cierre de ayer (horario normal). None si faltan días."""
    if len(previos) < 2:
        return None
    return float(previos[-1].c.iloc[-1]) / float(previos[-2].c.iloc[-1]) - 1


def sincronizar(sym, df, hoy, ahora, lotes):
    if not isinstance(lotes, dict):
        lotes = {'orb': lotes, 'ruido': lotes}
    hoy_df, previos = partir_dias(df, hoy)
    if len(hoy_df) == 0 or hoy_df.index[0].time() > T('09:35'):
        return
    r1 = caida_ayer(previos)
    sin_orb = r1 is not None and r1 < CAIDA_ORB
    sin_ruido = r1 is not None and r1 < CAIDA_RUIDO
    # --- Rango de 30 min ---
    niv = niveles_orb(hoy_df)
    if niv and ahora.time() >= T('10:00') and str(hoy) not in FOMC and not CONTEXTO.get('marcas', {}).get('decision_fed') and not sin_orb:
        hi, lo = niv
        lado_m, est = modelo_orb(hoy_df, hi, lo)
        lado_r, ps = posicion(sym, 'orb')
        pend = pendientes(sym, 'orb')
        if lado_r != 0:
            if pend:
                cancelar_pendientes(sym, 'orb', 'se llenó la del otro lado')
            if not entrada_anotada('orb', hoy):
                p = ps[0]; nivel = hi if lado_r > 0 else lo
                log('entrada', NOMBRE['orb'], 'compra' if lado_r > 0 else 'venta', p.volume, f'{p.price_open:.2f}',
                    f'se llenó la orden pendiente del rango de 30 min ({lo:,.2f}–{hi:,.2f}) · deslizamiento {(p.price_open - nivel) * lado_r:+.2f} pts · stop {p.sl:,.2f}')
            if est == 'stop' or (lado_m != 0 and lado_m != lado_r):
                cerrar(sym, 'orb', 'tocó el stop del rango de 30 min')
        elif opero_hoy('orb', hoy) or est in ('stop', 'ambos') or ahora.time() >= CIERRE:
            if pend:
                cancelar_pendientes(sym, 'orb', 'el rango ya se operó o ya no aplica hoy')
        elif est == 'esperando' and not pend:
            info, t = mt5.symbol_info(sym), mt5.symbol_info_tick(sym)
            dist = max(info.point, (info.trade_stops_level or 0) * info.point)
            if t is not None and t.ask + dist < hi + info.point and t.bid - dist > lo - info.point:
                rango = f'rango de 30 min ({lo:,.2f}–{hi:,.2f})'
                poner_pendiente(sym, 'orb', 1, lotes['orb'], hi + info.point, lo, 'compra si rompe arriba del ' + rango)
                poner_pendiente(sym, 'orb', -1, lotes['orb'], lo - info.point, hi, 'venta si rompe abajo del ' + rango)
        elif est == 'activo' and not pend:
            abrir(sym, 'orb', lado_m, lotes['orb'], lo if lado_m > 0 else hi,
                  f'rompió el rango de 30 min ({lo:,.2f}–{hi:,.2f}) sin orden pendiente: entra a mercado')
    # --- Zona de ruido ---
    cierre_ayer = float(previos[-1].c.iloc[-1]) if previos else None
    pos_m, info, ultimo = modelo_ruido(hoy_df, previos, cierre_ayer, ahora)
    if pos_m is None or sin_ruido:
        return
    lado_r, _ = posicion(sym, 'ruido')
    if lado_r == 0 and pos_m != 0 and salio_por_stop('ruido', ultimo):
        return                                   # el stop de emergencia la sacó: espera al siguiente chequeo
    if pos_m != lado_r:
        if lado_r != 0:
            cerrar(sym, 'ruido', 'salió de la zona · ' + info)
        if pos_m != 0:
            precio = mt5.symbol_info_tick(sym).ask if pos_m > 0 else mt5.symbol_info_tick(sym).bid
            abrir(sym, 'ruido', pos_m, lotes['ruido'], precio * (1 - STOP_EMERGENCIA * pos_m), 'cerró fuera de la zona de ruido · ' + info)


def proteger(sym, df):
    """Break even (rango 30 min) y escalera (zona de ruido): sube el stop en el servidor, nunca lo baja."""
    info, t = mt5.symbol_info(sym), mt5.symbol_info_tick(sym)
    if info is None or t is None:
        return
    usd_pt = DOLARES_POR_PUNTO
    for clave in MAGIC:
        _, ps = posicion(sym, clave)
        for p in ps:
            lado = 1 if p.type == mt5.POSITION_TYPE_BUY else -1
            desde = a_ny(p.time).replace(second=0, microsecond=0)
            desde = desde - dt.timedelta(minutes=desde.minute % 5)
            velas_pos = df[df.index > desde] if clave == 'orb' else df[df.index >= desde]   # ORB entra a media vela: su máximo previo no cuenta
            mejor = max([t.bid] + list(velas_pos.h)) if lado > 0 else min([t.ask] + list(velas_pos.l))
            maxima = (mejor - p.price_open) * lado * usd_pt
            piso = piso_usd(clave, maxima)
            if piso is None:
                continue
            nuevo = round(p.price_open + lado * piso / usd_pt, info.digits)
            if p.sl and ((lado > 0 and nuevo <= p.sl + info.point) or (lado < 0 and nuevo >= p.sl - info.point)):
                continue                                    # el stop ya está igual o mejor
            actual = t.bid if lado > 0 else t.ask
            minimo = (info.trade_stops_level or 0) * info.point
            if (lado > 0 and actual - nuevo <= minimo) or (lado < 0 and nuevo - actual <= minimo):
                cerrar(sym, clave, f'el precio ya está en el piso asegurado (+{piso:,.0f} USD)')
                continue
            r = mt5.order_send(dict(action=mt5.TRADE_ACTION_SLTP, symbol=sym, position=p.ticket, sl=nuevo, tp=p.tp or 0.0,
                                    magic=MAGIC[clave]))
            if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
                que = 'break even' if clave == 'orb' else f'escalera: asegura +{piso:,.0f} USD'
                log('protege', NOMBRE[clave], 'compra' if lado > 0 else 'venta', p.volume, f'{nuevo:.2f}',
                    f'{que} · llegó a ir +{maxima:,.0f} USD · stop de {p.sl:.2f} a {nuevo:.2f}')
            else:
                log('error', NOMBRE[clave], detalle=f"no pude mover el stop: {r.retcode if r else mt5.last_error()} {r.comment if r else ''}")


SACUDIDA = 0.006   # rango 30 min: si una vela de 5 min se mueve más de 0.6% EN CONTRA, sale al cierre de esa vela (8 años: Sharpe 1.24→1.35)
EVENTO_GIGANTES = 1.5    # día después de reporte de un gigante del Nasdaq (o antes de abrir): +$259/día vs +$112 normal (t 2.0)
COT_RECORTE = 0.5        # semana en que los fondos apalancados recortan fuerte (COT): el bot gana mucho menos (t≈2.5)
NFP_RUIDO = 1.5          # día de empleo (NFP): la zona de ruido gana 63% (+$38.9/trade vs $10.2)
# Juntas (8 años): $32.2→$37.9/día, Sharpe 1.59→1.75; reto FTMO 12 MNQ: promedio 12 m $26.4k→$29.2k, peor 10% $1.5k→$5.9k
CAIDA_RUIDO, CAIDA_ORB = -0.010, -0.020   # si ayer el Nasdaq cayó más que esto (cierre a cierre), no opera esa estrategia hoy
# 8 años, costos realistas: ayer < −1% → ruido −$17.5/trade; ayer < −2% → ORB −$16.9 y ruido −$40.4 (las dos mitades).
# Regla: $35.0→$37.4/día, Sharpe 1.62→1.80 (1.67/1.98); meseta entre −1% y −2%.
CIERRE_FUERTE, CIERRE_DEBIL = 0.8, 0.2     # zona de ruido: ×1.5 si ayer cerró en el 20% alto de su rango, ×0.5 si en el 20% bajo
# 8 años (ruido $/trade por posición del cierre de ayer: −2.6, 3.6, 8.0, 12.3, 20.7 — escalonado). Sobre todo lo anterior: $37.4→$41.0/día,
# Sharpe 1.80→1.81, caída −$4,454→−$3,987.
MIEDO_CORTO = 1.10   # VIX9D/VIX al cierre de ayer: arriba de esto, medio tamaño (8 años: esos días −$40/día vs +$35, t −2.4; Sharpe 1.50→1.57)


def sacudida(sym, df, hoy):
    """Detector de sacudidas (Trump, noticias, cualquier sorpresa): revisa la última vela de 5 min ya cerrada."""
    d = df[df.index.date == hoy]
    if len(d) < 3:
        return
    ult, ant = d.iloc[-2], d.iloc[-3]                 # la última es la que se está formando
    mov = ult.c / ant.c - 1
    if abs(mov) <= SACUDIDA:
        return
    lado, ps = posicion(sym, 'orb')
    if lado != 0 and ps:
        t0 = a_ny(ps[0].time).replace(second=0, microsecond=0)
        if d.index[-2] < t0 - dt.timedelta(minutes=t0.minute % 5):
            return                                    # esa vela es de antes de entrar: no cuenta (igual que la simulación)
    if lado != 0 and lado * mov < 0:
        cerrar(sym, 'orb', f'sacudida en contra: la vela de las {d.index[-2]:%H:%M} NY se movió {mov:+.2%}')


def anotar_salidas(sym, hoy, est):
    """Anota en la bitácora las salidas que hizo el servidor solo (stop, break even, escalera, stop de emergencia)."""
    hechas = est.setdefault('dia', {}).setdefault('salidas_srv', [])
    ds = mt5.history_deals_get(dt.datetime.now(UTC) - dt.timedelta(days=2), dt.datetime.now(UTC) + dt.timedelta(days=1)) or []
    razones = {mt5.DEAL_REASON_SL: 'stop', mt5.DEAL_REASON_TP: 'objetivo', mt5.DEAL_REASON_SO: 'falta de margen'}
    for dl in ds:
        clave = next((k for k, v in MAGIC.items() if v == dl.magic), None)
        tk = getattr(dl, 'ticket', None)
        if clave is None or dl.entry != mt5.DEAL_ENTRY_OUT or dl.reason not in razones or tk in hechas or a_ny(dl.time).date() != hoy:
            continue
        hechas.append(tk)
        res = getattr(dl, 'profit', 0.0) + getattr(dl, 'commission', 0.0) + getattr(dl, 'swap', 0.0)
        log('salida', NOMBRE[clave], 'venta' if getattr(dl, 'type', None) == mt5.DEAL_TYPE_SELL else 'compra', getattr(dl, 'volume', ''),
            f"{getattr(dl, 'price', 0.0):.2f}", f'la cerró el servidor por {razones[dl.reason]} · resultado {res:+,.2f} USD')


def cerrar_viejas(sym, hoy):
    for clave in MAGIC:
        _, ps = posicion(sym, clave)
        if any(a_ny(p.time).date() < hoy for p in ps):
            cerrar(sym, clave, 'quedó abierta de un día anterior')


def resumen(sym, hoy):
    acc = mt5.account_info()
    ds = mt5.history_deals_get(dt.datetime.now(UTC) - dt.timedelta(days=2), dt.datetime.now(UTC) + dt.timedelta(days=1)) or []
    L = [f"📊 Update del bot Nasdaq{' FTMO' if CUENTA == 'ftmo' else ' (reglas FTMO)' if MODO == 'ftmo' else ''} — {hoy:%d-%m-%Y}", f'💰 Cuenta: ${acc.equity:,.2f}']
    total = 0.0
    for clave in MAGIC:
        mios = [d for d in ds if d.magic == MAGIC[clave] and a_ny(d.time).date() == hoy]
        pnl = sum(d.profit + d.commission + d.swap + getattr(d, 'fee', 0.0) for d in mios)
        n = sum(1 for d in mios if d.entry == mt5.DEAL_ENTRY_IN)
        total += pnl
        L.append(f"• {NOMBRE[clave]}: {'sin operaciones' if n == 0 else f'{n} operación(es) · {pnl:+,.2f} USD'}")
    L.append(f'🧮 Total del día: {total:+,.2f} USD (base {CONTRATOS} MNQ por estrategia, ajustado por volatilidad)')
    L += ftmo_cierre(acc.equity, hoy) if MODO == 'ftmo' else cerrar_dia_examen(acc.equity, hoy)
    errores = 0
    try:
        with open(BITACORA, encoding='utf-8') as fh:
            errores = sum(1 for f in csv.DictReader(fh) if f['evento'] == 'error' and f['hora_UTC'][:10] >= f'{hoy:%Y-%m-%d}')
    except Exception:
        pass
    L.append(f'⚠️ {errores} error(es) hoy: revisa {os.path.basename(BITACORA)}' if errores else '✅ Sin errores')
    texto = '\n'.join(L)
    log('resumen', detalle=texto.replace('\n', ' | '))
    publicar(texto)


def cerrar_dia_examen(equity, hoy):
    """Aplica las reglas del examen de Lucid al cierre del día a las 3 versiones y devuelve las líneas para el resumen."""
    e = leer_estado(); d = e.get('dia', {}); V = e.get('versiones', {})
    if not V or 'v' not in d:
        return []
    R = equity - d.get('eq_inicio', equity)
    L = []
    for v, base in VERSIONES.items():
        x, s = V[v], d['v'][v]
        r = s['fijo'] if s['fijo'] is not None else R * s['f']
        tag = f"{v} (base {base}, hoy {s['n']} MNQ)"
        if s['quemado']:
            e.setdefault('historial', []).append(dict(version=v, n=x['n'], inicio=x['inicio'], fin=str(hoy), dias=x['dias'] + 1, resultado='quemado'))
            L.append(f"🔥 {tag}: examen #{x['n']} QUEMADO hoy ({r:+,.0f}) tras {x['dias'] + 1} días. Mañana arranca el #{x['n'] + 1}.")
            examen_nuevo(e, v, hoy, x['n'])
            continue
        x['saldo'] += r; x['dias'] += 1; x['mejor_dia'] = max(x['mejor_dia'], r); bal = x['saldo']
        if not x['bloq']:
            x['alto'] = max(x['alto'], bal); x['mll'] = x['alto'] - EXAMEN_MLL
            if bal > EXAMEN_BLOQUEO:
                x['mll'] = 100.0; x['bloq'] = True
        if bal >= EXAMEN_META and x['mejor_dia'] <= 0.5 * bal:
            e.setdefault('historial', []).append(dict(version=v, n=x['n'], inicio=x['inicio'], fin=str(hoy), dias=x['dias'], resultado='aprobado'))
            L.append(f"🏆 {tag}: examen #{x['n']} APROBADO en {x['dias']} días (+${bal:,.0f}). Mañana arranca el #{x['n'] + 1}.")
            examen_nuevo(e, v, hoy, x['n'])
        else:
            falta = '' if bal < EXAMEN_META else ' (pasó la meta, pero un día pesa más del 50%)'
            L.append(f"🎯 {tag}: examen #{x['n']} · día {x['dias']} · hoy {r:+,.0f} · lleva {bal:+,.0f} de +3,000{falta} · margen ${bal - x['mll']:,.0f}")
    h = e.get('historial', [])
    if h:
        L.append('📈 Exámenes terminados: ' + ' · '.join(
            f"{v}: {sum(1 for z in h if z.get('version') == v and z['resultado'] == 'aprobado')} aprobados de {sum(1 for z in h if z.get('version') == v)}" for v in VERSIONES))
    guardar_estado(e)
    return L


def ftmo_fase_nueva(e, fase, equity, hoy):
    viejo = e.get('ftmo') or {}
    e['ftmo'] = dict(fase=fase, inicio=str(hoy), base=equity, cierre_prev=equity, dias=0, listo=False,
                     login=viejo.get('login'), etapa=viejo.get('etapa'))


def ftmo_dia(e, eq, hoy):
    """Meta y pisos del día en el reto FTMO. La fase 2 se simula sobre la misma cuenta, con nueva base."""
    f = e['ftmo']; ini = FTMO_INICIAL
    obj = f['base'] + (0.10 if f['fase'] == 1 else 0.05) * ini
    piso = max(eq - 0.05 * ini, f['base'] - 0.10 * ini)   # pérdida diaria (vs saldo al empezar el día; sin posiciones de noche) o máxima (fija)
    if ETAPA == 'fondeada':
        meta = 1e12                                         # cuenta fondeada: sin meta del día
    else:
        meta = 50.0 if f['listo'] else max(obj - eq + 50.0, 100.0)
    return dict(fecha=str(hoy), eq_inicio=eq, min_eq=eq, cerrado=False, quemado=False, meta=meta, piso=piso, obj=obj)


def ftmo_cierre(equity, hoy):
    e = leer_estado(); f = e.get('ftmo'); d = e.get('dia', {})
    if not f:
        return []
    ini = FTMO_INICIAL; L = []
    agotado = ETAPA != 'fondeada' and equity <= f['base'] - (0.10 - 2 * FTMO_FRENO) * ini
    if d.get('quemado') and not agotado:
        L.append(f"🛑 Reto FTMO fase {f['fase']}: tocó el freno 0.4% antes del límite (equity {equity:,.0f}); la cuenta sigue viva, mañana sigue.")
    if agotado:
        e.setdefault('historial_ftmo', []).append(dict(fase=f['fase'], inicio=f['inicio'], fin=str(hoy), resultado='agotado', dias=f['dias'] + 1))
        if ETAPA == 'reto':
            L.append(f"🔥 Reto FTMO fase {f['fase']} AGOTADO: quedan menos de {2 * FTMO_FRENO:.1%} antes de la pérdida máxima. "
                     f"En real = reto perdido. Mañana arranca un reto nuevo (como comprar otro).")
            ftmo_fase_nueva(e, 1, equity, hoy); guardar_estado(e); return L
        f['aprobada'] = 'agotado'
        L.append(f"🔥 Reto FTMO fase {f['fase']} AGOTADO (equity {equity:,.0f}): el bot deja de operar esta cuenta. Compra un reto nuevo, cambia los secretos y BOT_FTMO_ETAPA.")
        guardar_estado(e); return L
    f['dias'] += 1; f['cierre_prev'] = equity
    gan = equity - f['base']; obj = (0.10 if f['fase'] == 1 else 0.05) * ini
    if ETAPA == 'fondeada':
        L.append(f"💼 Cuenta FTMO fondeada · día {f['dias']} · {gan:+,.0f} desde el inicio · pérdida máxima en {f['base'] - 0.10 * ini:,.0f}")
        guardar_estado(e); return L
    if gan >= obj:
        f['listo'] = True
    if f['listo'] and f['dias'] >= 4:
        e.setdefault('historial_ftmo', []).append(dict(fase=f['fase'], inicio=f['inicio'], fin=str(hoy), resultado='aprobada', dias=f['dias']))
        if ETAPA in ('fase1', 'fase2'):
            f['aprobada'] = True
            L.append(f"🏆 FASE {f['fase']} APROBADA en {f['dias']} días (+${gan:,.0f}). El bot deja de operar esta cuenta: "
                     f"pide la siguiente en FTMO, cambia los secretos FTMO_* y BOT_FTMO_ETAPA.")
        elif f['fase'] == 1:
            L.append(f"🏆 FASE 1 APROBADA en {f['dias']} días (+${gan:,.0f}). Mañana arranca la fase 2 (meta +5%).")
            ftmo_fase_nueva(e, 2, equity, hoy)
        else:
            L.append(f"🏆🏆 FASE 2 APROBADA en {f['dias']} días (+${gan:,.0f}): en FTMO real ya serías cuenta fondeada.")
            ftmo_fase_nueva(e, 1, equity, hoy)
    else:
        piso = max(equity - 0.05 * ini, f['base'] - 0.10 * ini)
        L.append(f"🎯 Reto FTMO fase {f['fase']} · día {f['dias']} · lleva {gan:+,.0f} de +{obj:,.0f}"
                 f"{' (meta lograda, completa los 4 días mínimos)' if f['listo'] else ''} · margen mañana ${equity - piso:,.0f}")
    guardar_estado(e)
    return L


def publicar(texto):
    token, repo = os.environ.get('GH_TOKEN', ''), os.environ.get('GITHUB_REPOSITORY', '')
    if not (token and repo):
        return
    titulo = '📊 Update diario del bot Nasdaq' + (' FTMO' if CUENTA == 'ftmo' else '')
    def gh(metodo, ruta, datos=None):
        req = urllib.request.Request(f'https://api.github.com/repos/{repo}{ruta}', method=metodo,
                                     data=json.dumps(datos).encode() if datos is not None else None,
                                     headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                                              'User-Agent': 'bot-nasdaq', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            t = r.read()
        return json.loads(t) if t else None
    try:
        issues = gh('GET', '/issues?state=open&per_page=100') or []
        n = next((i['number'] for i in issues if i.get('title') == titulo and 'pull_request' not in i), None)
        if n is None:
            n = gh('POST', '/issues', {'title': titulo, 'body': 'Aquí el bot deja su resumen al final de cada día de bolsa.'})['number']
        dueno = os.environ.get('GITHUB_REPOSITORY_OWNER', '')
        gh('POST', f'/issues/{n}/comments', {'body': (f'@{dueno}\n\n' if dueno else '') + texto})
        print(f'Resumen publicado en el issue #{n}.')
    except Exception as e:
        print(f'::warning::No pude publicar el resumen: {e!r}'[:300])


def prueba():
    """Se conecta, revisa todo y muestra lo que habría hecho el modelo el último día de bolsa. NO opera."""
    if not iniciar() or mt5.account_info() is None:
        print(f'❌ No pude conectar con MT5 ({mt5.last_error()}): revisa los secretos MT5_LOGIN, MT5_PASSWORD y MT5_SERVER.'); sys.exit(1)
    acc = mt5.account_info()
    print(f"✅ Conectado a la cuenta {acc.login} ({acc.server}) · {'DEMO' if acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else 'REAL (el bot no operaría)'}"
          f" · equity {acc.equity:,.2f} {acc.currency} · apalancamiento 1:{acc.leverage}")
    sym = buscar_simbolo()
    if sym is None:
        print('❌ No encontré el Nasdaq-100 (USTEC).'); sys.exit(1)
    calcular_desfase(sym); info = mt5.symbol_info(sym); t = mt5.symbol_info_tick(sym)
    print(f'✅ Símbolo {sym} · {lotes_por_mnq(info):g} lotes por estrategia (≈1 MNQ) · spread {t.ask - t.bid:.2f} puntos · '
          f'servidor {DESFASE / 3600:+.0f} h respecto a Nueva York')
    df = velas(sym)
    if df is None or len(df) == 0:
        print('❌ MT5 no dio velas de 5 min.'); sys.exit(1)
    dias = sorted({d for d in df.index.date if str(d) not in FERIADOS})
    ultimo = dias[-1]
    hoy_df, previos = partir_dias(df, ultimo)
    print(f'✅ Historia: {len(previos)} días completos antes del {ultimo} (se necesitan 14)')
    n, peso, vh, vm = contratos_hoy(sym)
    print(f"{'✅' if vh else '⚠️'} Volatilidad (horario normal, 14 días): {vh if vh is None else f'{vh:.2%}'} vs normal {vm if vm is None else f'{vm:.2%}'} → peso {peso:.2f} → {n} MNQ con base {CONTRATOS}")
    niv = niveles_orb(hoy_df)
    if niv:
        lado, est = modelo_orb(hoy_df, *niv)
        print(f"   {ultimo} · rango 30 min {niv[1]:,.2f}–{niv[0]:,.2f} → {'compra' if lado > 0 else 'venta' if lado < 0 else 'sin operación'} ({est})")
    fin = dt.datetime.combine(ultimo, T('15:55'))
    pos, txt, _ = modelo_ruido(hoy_df, previos, float(previos[-1].c.iloc[-1]) if previos else None, fin)
    print(f"   {ultimo} · zona de ruido al final del día: {'—' if pos is None else {1: 'comprado', -1: 'vendido', 0: 'fuera'}[pos]} · {txt}")
    print('✅ Prueba terminada sin operar.')
    mt5.shutdown()


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    if '--prueba' in sys.argv:
        return prueba()
    ahora = ahora_ny(); hoy = ahora.date()
    if hoy.weekday() >= 5 or str(hoy) in FERIADOS:
        print(f'{hoy}: no hay bolsa en Nueva York. No hago nada.'); return
    cierre = T('12:55') if str(hoy) in MEDIO_DIA else CIERRE
    hasta = FIN_MANANA if ahora.time() < T('12:30') else (dt.datetime.combine(hoy, cierre) + dt.timedelta(minutes=3)).time()
    tramo = 'mañana' if hasta == FIN_MANANA else 'tarde'
    if str(hoy) in MEDIO_DIA:          # la bolsa cierra a las 13:00: el tramo de la mañana se queda hasta el cierre (no deja posiciones al de la tarde)
        hasta = (dt.datetime.combine(hoy, cierre) + dt.timedelta(minutes=3)).time()
    if not iniciar() or mt5.account_info() is None:
        log('error', detalle=f'no pude conectar con MT5 ({mt5.last_error()})'); sys.exit(1)
    acc = mt5.account_info()
    if acc.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        if CUENTA == 'ftmo' and 'ftmo' in (getattr(acc, 'server', '') or '').lower():
            log('aviso', detalle=f'cuenta FTMO {acc.login} marcada como real en MT5 (capital simulado de FTMO): opero')
        else:
            log('error', detalle=f'la cuenta {acc.login} NO es demo: este bot solo opera en demo'); sys.exit(1)
    sym = buscar_simbolo()
    if sym is None:
        log('error', detalle='no encontré el Nasdaq-100 (USTEC) en MT5'); sys.exit(1)
    calcular_desfase(sym)
    info = mt5.symbol_info(sym)
    global CONTEXTO
    CONTEXTO = leer_contexto(hoy)
    n_mnq, peso, v_hoy, v_med = contratos_hoy(sym)
    # Tamaño = base × (todos los factores multiplicados) y se redondea UNA vez, igual que la simulación (final2.py: round(base × mo))
    f_orb = peso
    r9 = (CONTEXTO.get('marcas') or {}).get('vix9d_vix') if CONTEXTO else None
    if r9 and r9 > MIEDO_CORTO:
        f_orb *= 0.5
        log('tamaño', detalle=f'VIX 9 días / VIX 30 días = {r9:.3f} > {MIEDO_CORTO} (miedo de corto plazo) → ×0.5')
    f_ev, nfp, motivos = factor_evento()
    if f_ev != 1.0:
        f_orb *= f_ev
        log('tamaño', detalle=f"{' y '.join(motivos)} → ×{f_ev:g}")
    f_ruido = f_orb
    try:
        _, prev0 = partir_dias(velas(sym), hoy)
        ay = prev0[-1]; pos_ayer = (float(ay.c.iloc[-1]) - float(ay.l.min())) / max(float(ay.h.max() - ay.l.min()), 1e-9)
        f_c = 1.5 if pos_ayer > CIERRE_FUERTE else 0.5 if pos_ayer < CIERRE_DEBIL else 1.0
        if f_c != 1.0:
            f_ruido *= f_c
            log('tamaño', detalle=f"ayer cerró en el {pos_ayer:.0%} de su rango → zona de ruido ×{f_c:g}")
    except Exception as e:
        log('aviso', detalle=f'no pude revisar el cierre de ayer ({e})')
    if nfp:
        f_ruido *= NFP_RUIDO
        log('tamaño', detalle=f'día de empleo (NFP): zona de ruido ×{NFP_RUIDO:g}')
    if MODO == 'ftmo' and (f_orb > TOPE_FTMO or f_ruido > TOPE_FTMO):   # FTMO revisa tamaños «mucho más grandes» que los habituales
        log('tamaño', detalle=f'tope FTMO: máximo {TOPE_FTMO:g}× la base ({CONTRATOS} MNQ) por estrategia')
        f_orb, f_ruido = min(f_orb, TOPE_FTMO), min(f_ruido, TOPE_FTMO)
    n_mnq, n_ruido = max(1, round(CONTRATOS * f_orb)), max(1, round(CONTRATOS * f_ruido))
    paso, lpm = info.volume_step or 0.01, lotes_por_mnq(info)
    lotes, lotes_ruido = (round(round(lpm * n / paso) * paso, 8) for n in (n_mnq, n_ruido))
    if info.volume_max and max(lotes, lotes_ruido) > info.volume_max:
        log('aviso', detalle=f'{max(lotes, lotes_ruido)} lotes pasa el máximo por orden del símbolo ({info.volume_max}); uso {info.volume_max}')
        lotes, lotes_ruido = min(lotes, float(info.volume_max)), min(lotes_ruido, float(info.volume_max))
    if v_hoy:
        log('tamaño', detalle=f'volatilidad 14 días {v_hoy:.2%} vs normal {v_med:.2%} → peso {peso:.2f} · '
                              f'hoy: rango 30 min {n_mnq} MNQ ({lotes:g} lotes) · zona de ruido {n_ruido} MNQ ({lotes_ruido:g} lotes)')
    est = leer_estado()
    est.pop('examen', None)
    if MODO == 'ftmo':
        f0 = est.get('ftmo') or {}
        if f0 and f0.get('login') is None:            # estado de antes de este cambio: es la misma cuenta
            f0['login'], f0['etapa'] = acc.login, ETAPA
        if not f0 or f0.get('login') != acc.login or (f0.get('etapa') or 'reto') != ETAPA:
            if f0:
                log('aviso', detalle=f"cuenta o etapa nueva (login {acc.login}, etapa {ETAPA}) → reinicio el seguimiento FTMO con balance {acc.balance:,.2f}")
            est['ftmo'] = dict(login=acc.login, etapa=ETAPA)
            est.pop('dia', None)
            ftmo_fase_nueva(est, 2 if ETAPA == 'fase2' else 1, acc.balance, hoy)
        if est['ftmo'].get('aprobada'):
            que = 'agotada (sin margen antes de la pérdida máxima)' if est['ftmo']['aprobada'] == 'agotado' else 'ya aprobada'
            log('aviso', detalle=f"fase {est['ftmo']['fase']} {que} en esta cuenta: no opero. Cambia a la siguiente cuenta y BOT_FTMO_ETAPA.")
            guardar_estado(est); mt5.shutdown(); return
        if est.get('dia', {}).get('fecha') != str(hoy):
            est['dia'] = ftmo_dia(est, acc.equity, hoy)
        if est['ftmo']['listo'] and ETAPA != 'fondeada':
            n_mnq = 1
            lotes = lotes_ruido = round(round(lotes_por_mnq(info) / (info.volume_step or 0.01)) * (info.volume_step or 0.01), 8)
        guardar_estado(est)
        dd = est['dia']
        meta_txt = f"FTMO {'fondeada · sin meta' if ETAPA == 'fondeada' else 'fase ' + str(est['ftmo']['fase']) + ' · meta del día +' + format(dd['meta'], ',.0f')} · freno en equity {dd['piso'] + FTMO_FRENO * FTMO_INICIAL:,.0f}"
    for v in (VERSIONES if MODO != 'ftmo' else {}):
        if v not in est.get('versiones', {}):
            examen_nuevo(est, v, hoy)
    if MODO != 'ftmo' and (est.get('dia', {}).get('fecha') != str(hoy) or 'v' not in est.get('dia', {})):
        vs = {}
        for v, base in VERSIONES.items():
            n_v = max(1, round(base * peso))
            if r9 and r9 > MIEDO_CORTO:
                n_v = max(1, round(n_v * 0.5))
            n_v = max(1, round(n_v * f_ev))
            vs[v] = dict(n=n_v, f=n_v / n_mnq, meta=meta_del_dia(est['versiones'][v]['saldo']), fijo=None, quemado=False)
        est['dia'] = dict(fecha=str(hoy), eq_inicio=acc.equity, min_eq=acc.equity, cerrado=False, v=vs)
    guardar_estado(est)
    if MODO != 'ftmo':
        meta_txt = ' · '.join(f"{v} {s['n']} MNQ meta +{s['meta']:,.0f}" for v, s in est['dia']['v'].items())
    log('inicio', detalle=f'tramo de la {tramo} · {sym} · {lotes:g} lotes por estrategia (≈{n_mnq} MNQ) · equity {acc.equity:,.2f} · '
                          f'{meta_txt} · '
                          f'cuenta demo · trabaja hasta las {hasta:%H:%M} NY')
    try:
        _, prev0 = partir_dias(velas(sym), hoy)
        r1 = caida_ayer(prev0)
        if r1 is not None and r1 < CAIDA_RUIDO:
            log('filtro', detalle=f'ayer el Nasdaq cerró {r1:+.2%}: hoy no opera la zona de ruido' + (' ni el rango de 30 min' if r1 < CAIDA_ORB else ''))
    except Exception as e:
        log('aviso', detalle=f'no pude revisar la caída de ayer ({e})')
    if CONTEXTO:
        m = CONTEXTO.get('marcas', {})
        evs = ', '.join(f"{e['hora_mx']} {e['evento']}" for e in (CONTEXTO.get('calendario') or [])) or 'sin eventos'
        log('contexto', detalle=f"{evs} · reportaron ayer: {m.get('gigantes_reportaron_ayer_tras_cierre')} · hoy: "
                                f"{m.get('gigantes_reportan_hoy_antes')} / {m.get('gigantes_reportan_hoy_tras_cierre')} · VIX {m.get('vix')}"
                                + (' · DÍA DE DECISIÓN DE LA FED: no opera el rango de 30 min' if m.get('decision_fed') else ''))
    else:
        log('aviso', detalle='SIN CONTEXTO del día (no llegó contexto/hoy.json): sin filtro de Fed por contexto ni recorte por VIX9D')
    cerrar_viejas(sym, hoy)
    errores = 0
    while True:
        ahora = ahora_ny()
        if ahora.time() >= cierre:
            for clave in MAGIC:
                cerrar(sym, clave, f'cierre del día ({cierre:%H:%M} NY)')
            guardar_estado(est)
            if leer_estado().get('dia', {}).get('resumido') == str(hoy):
                print('El resumen de hoy ya se publicó (otro tramo): no lo repito.')
            else:
                resumen(sym, hoy)
                e2 = leer_estado(); e2.setdefault('dia', {})['resumido'] = str(hoy); guardar_estado(e2)
            break
        if ahora.time() >= hasta:
            guardar_estado(est)
            log('fin', detalle=f'termina el tramo de la {tramo}; el de la tarde sigue con las posiciones abiertas')
            break
        try:
            if not conectado():
                raise RuntimeError(f'sin conexión con MT5 ({mt5.last_error()})')
            eq = mt5.account_info().equity
            d = est['dia']
            if eq < d['min_eq']:
                d['min_eq'] = eq
            R = eq - d['eq_inicio']
            if MODO == 'ftmo' and not d['cerrado']:
                if eq <= d['piso'] + FTMO_FRENO * FTMO_INICIAL:
                    for clave in MAGIC:
                        cerrar(sym, clave, f'FRENO FTMO: equity {eq:,.0f} a menos de {FTMO_FRENO:.1%} del límite ({d["piso"]:,.0f})')
                    d['cerrado'] = d['quemado'] = True
                    log('examen', detalle=f'freno FTMO: equity {eq:,.2f} · límite {d["piso"]:,.2f}'); guardar_estado(est)
                elif R >= d['meta']:
                    for clave in MAGIC:
                        cerrar(sym, clave, f'meta del día alcanzada (+{R:,.0f} USD)')
                    d['cerrado'] = True
                    log('meta', detalle=f'meta del día FTMO +{d["meta"]:,.0f} alcanzada ({R:+,.0f})'); guardar_estado(est)
            for v, s in (d['v'].items() if MODO != 'ftmo' else []):
                if s['fijo'] is not None:
                    continue
                x, p = est['versiones'][v], R * s['f']
                if x['saldo'] + p <= x['mll']:
                    s['fijo'], s['quemado'] = p, True
                    log('examen', detalle=f"versión {v} ({s['n']} MNQ): examen #{x['n']} quemado ({p:+,.0f} hoy, saldo {x['saldo'] + p:+,.0f})")
                    guardar_estado(est)
                elif p >= s['meta']:
                    s['fijo'] = p
                    log('meta', detalle=f"versión {v} ({s['n']} MNQ): meta del día +{s['meta']:,.0f} alcanzada ({p:+,.0f})")
                    guardar_estado(est)
            if MODO != 'ftmo' and not d['cerrado'] and all(s['fijo'] is not None for s in d['v'].values()):
                for clave in MAGIC:
                    cerrar(sym, clave, 'las 3 versiones terminaron su día (meta o quemado)')
                d['cerrado'] = True
                guardar_estado(est)
            df = velas(sym)
            if df is not None and not d['cerrado']:
                sincronizar(sym, df, hoy, ahora, {'orb': lotes, 'ruido': lotes_ruido})
                sacudida(sym, df, hoy)
                proteger(sym, df)
            anotar_salidas(sym, hoy, est)
            errores = 0
        except Exception as e:
            errores += 1
            if errores in (1, 10, 50):
                log('error', detalle=f'{type(e).__name__}: {e}'[:200])
        try:
            time.sleep(2 if pendientes(sym, 'orb') else 10)
        except Exception:
            time.sleep(10)
    mt5.shutdown()


if __name__ == '__main__':
    main()
