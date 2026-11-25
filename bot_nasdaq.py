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
import os, re, sys, csv, json, math, time, base64, hashlib, threading, datetime as dt, urllib.request, urllib.error
from zoneinfo import ZoneInfo
import pandas as pd
import MetaTrader5 as mt5
from estrategias import niveles_orb, modelo_orb, modelo_ruido, piso_usd, LOOK, VELAS_DIA_MIN, T

HERE = os.path.dirname(os.path.abspath(__file__))
NY, UTC, PRAGA = ZoneInfo('America/New_York'), dt.timezone.utc, ZoneInfo('Europe/Prague')   # FTMO reinicia el día a medianoche de Praga
TZ_SERVIDOR = ZoneInfo(os.environ['BOT_TZ_SERVIDOR']) if os.environ.get('BOT_TZ_SERVIDOR') else None   # opcional: zona del servidor MT5 si no va 7 h adelante de NY todo el año
SIMBOLOS = ['USTEC', 'US100.cash', 'NAS100', 'US100', 'USTECH', 'NDX100']
# Cuenta: 'tickmill' (demo, 3 versiones del examen de Lucid) o 'ftmo' (reto FTMO 2-Step real: metas 10% y 5%, pérdida diaria 5%, máxima 10% fija)
CUENTA = os.environ.get('BOT_CUENTA', 'tickmill').lower()
SUF = '' if CUENTA == 'tickmill' else f'_{CUENTA}'
MODO = (os.environ.get('BOT_MODO') or ('ftmo' if CUENTA == 'ftmo' else 'lucid')).lower()   # reglas que sigue: ftmo | lucid (independiente de la cuenta)
BITACORA = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'bitacora_nasdaq{SUF}.csv')
FTMO_INICIAL = float(os.environ.get('BOT_FTMO_INICIAL', '100000'))   # capital inicial de la cuenta FTMO
ETAPA = os.environ.get('BOT_FTMO_ETAPA', 'reto')   # reto (fase 1 y 2 simuladas en la misma cuenta) | fase1 | fase2 | fondeada
ESCALA_FTMO = FTMO_INICIAL / 100000.0   # colchones de meta y tamaño de relleno proporcionales al capital (100K = 1.0: sin cambios)
TOPE_FTMO = 2.0      # máximo 2× la base por estrategia en FTMO (8 años: −5–8% de profit, misma probabilidad de cobrar)
FTMO_APALANCAMIENTO = float(os.environ.get('BOT_FTMO_APALANCAMIENTO', '15'))   # FTMO Swing: 1:15 en índices (Standard 1:50)
TOPE_POSICION_USD = 0.045 * FTMO_INICIAL if MODO == 'ftmo' else None   # stop de seguridad en el servidor: ninguna posición pierde más de $4,500 (100K) si el bot se cae
TOPE_MIN_USD = 0.005 * FTMO_INICIAL   # si queda menos margen que esto antes del freno, no abre (el stop no tendría espacio)
COLCHON_PTS = 30                     # freno FTMO: colchón mínimo de 30 pts × $/pt abierto (cubre el ciclo de 2 s y el deslizamiento al cerrar)
MARGEN_RESERVA = 0.85          # usa como máximo 85% del margen libre al abrir
AGOTADO = 0.02                  # reto/fase1/fase2. Fondeada: AGOTADO_FONDEADA (sin meta, toda ganancia se cobra; 8 años: igual o +$0.1k).
AGOTADO_FONDEADA = 0.008
# cuenta agotada si quedan < 2% antes de la pérdida máxima (antes 0.8%): 8 años, mediana +$0.3k / +$2.9k, no cobra 14% / 25% (auditoria-reglas.md)
FTMO_FRENO = 0.004              # cierra todo al quedar a 0.4% del capital de los límites de FTMO (tocarlos = cuenta perdida)
DOLARES_POR_PUNTO = 2.0          # 1 MNQ = US$2 por punto del Nasdaq-100
# ===== Modo examen (desde el 18-nov-2026): agresivo pero con reglas, simulando el examen de Lucid Flex 50K =====
CONTRATOS = float(os.environ.get('BOT_MNQ', '4'))                 # MNQ por estrategia que opera la demo (= versión B)
# 3 versiones del examen en paralelo con los mismos trades (escaladas): A 3 MNQ, B 4 MNQ, C 6 MNQ. La demo opera B y solo cierra
# todo cuando las 3 terminaron su día (meta o quemado). Simulación 8 años: B la más robusta; ver claude/mnq-lucid.md.
VERSIONES = {'A': 3, 'B': 4, 'C': 6}
META_DIARIA = float(os.environ.get('BOT_META_DIARIA', '1550'))   # al ganar esto en el día, cierra todo y para hasta mañana
EXAMEN_META, EXAMEN_MLL, EXAMEN_BLOQUEO = 3000.0, 2000.0, 2100.0  # reglas de Lucid Flex 50K
ESTADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'estado_nasdaq{SUF}.json')
MAGIC = {'orb': 301, 'ruido': 302}
NOMBRE = {'orb': 'Rango 30 min', 'ruido': 'Zona de ruido'}
STOP_EMERGENCIA = 0.01           # zona de ruido: stop en el servidor a 1% en contra (por si el bot se cae con la posición abierta)
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


def id_cuenta(login):
    """Identificador de la cuenta sin exponer el login (el repo es público)."""
    return hashlib.sha256(f'mt5:{login}'.encode()).hexdigest()[:12]


def ftmo_estado_es_de(f0, login, etapa):
    """True si el seguimiento FTMO guardado es de esta cuenta y esta etapa; si no, se reinicia.
    AUDIT_014 A1: un estado sin login (de antes del identificador) NO se adopta: podría ser de otra cuenta."""
    return bool(f0) and f0.get('login') == id_cuenta(login) and (f0.get('etapa') or 'reto') == etapa


def cuenta_txt(login):
    s = str(login)
    return f'…{s[-3:]}' if len(s) > 3 else s


def ahora_ny():
    return dt.datetime.now(NY).replace(tzinfo=None)


SUBIR_EN_VIVO = (os.environ.get('GITHUB_ACTIONS') == 'true' and bool(os.environ.get('GH_TOKEN')) and bool(os.environ.get('GITHUB_REPOSITORY'))
                 and os.environ.get('PRUEBA') != 'true' and os.environ.get('BOT_SUBIR_ESTADO', '1') != '0' and '--prueba' not in sys.argv)
_SUBIDA = {'pend': False, 'ult': 0.0, 'sha': {}, 'hilo': None}


def _api_contenido(metodo, ruta, cuerpo=None):
    url = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/contents/{ruta}" + ('?ref=main' if metodo == 'GET' else '')
    req = urllib.request.Request(url, method=metodo, data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                 headers={'Authorization': f"Bearer {os.environ['GH_TOKEN']}", 'Accept': 'application/vnd.github+json',
                                          'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode() or '{}')


_ARCHIVOS = threading.Lock()   # en Windows, os.replace falla si otro hilo tiene el archivo abierto (AUDIT_010 A3)


def _subir_archivo(local):
    """Sube un archivo a main con la API (sin git): si el runner muere a media sesión, el estado y la bitácora quedan guardados."""
    ruta = os.path.basename(local)
    with _ARCHIVOS:
        with open(local, 'rb') as fh:
            contenido = base64.b64encode(fh.read()).decode()
    for _ in range(3):
        sha = _SUBIDA['sha'].get(ruta)
        if sha is None:
            try:
                sha = _api_contenido('GET', ruta).get('sha')
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
        cuerpo = dict(message=f'Estado en vivo Nasdaq ({CUENTA}) {dt.datetime.now(UTC):%Y-%m-%d %H:%M} UTC', content=contenido, branch='main')
        if sha:
            cuerpo['sha'] = sha
        try:
            _SUBIDA['sha'][ruta] = _api_contenido('PUT', ruta, cuerpo)['content']['sha']
            return True
        except urllib.error.HTTPError as e:
            if e.code in (409, 422):                      # alguien más lo cambió: relee el sha y reintenta
                _SUBIDA['sha'].pop(ruta, None); continue
            raise
    return False


def _hilo_subida():
    while True:
        time.sleep(5)
        if _SUBIDA['pend'] and time.time() - _SUBIDA['ult'] >= 60:
            _SUBIDA['pend'], _SUBIDA['ult'] = False, time.time()
            for f in (ESTADO, BITACORA):
                try:
                    if os.path.exists(f) and not _subir_archivo(f):
                        _SUBIDA['pend'] = True                # 3 choques seguidos (409/422): lo reintenta en la próxima vuelta
                except Exception as e:                   # no detiene al bot: lo reintenta en la próxima subida
                    _SUBIDA['pend'] = True
                    print(f'aviso: no pude subir {os.path.basename(f)} al repo ({e})', flush=True)


def marcar_subida():
    """Pide subir estado y bitácora (como máximo cada 60 s, en segundo plano)."""
    if not SUBIR_EN_VIVO:
        return
    _SUBIDA['pend'] = True
    if _SUBIDA['hilo'] is None:
        _SUBIDA['hilo'] = threading.Thread(target=_hilo_subida, daemon=True)
        _SUBIDA['hilo'].start()


def log(evento, estrategia='', lado='', lotes='', precio='', detalle=''):
    f = BITACORA; nuevo = not os.path.exists(f)
    fila = [dt.datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S'), evento, estrategia, lado, lotes, precio, detalle]
    with _ARCHIVOS, open(f, 'a', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if nuevo:
            w.writerow(['hora_UTC', 'evento', 'estrategia', 'lado', 'lotes', 'precio', 'detalle'])
        w.writerow(fila)
    print(' | '.join(str(x) for x in fila if x != ''), flush=True)
    marcar_subida()


# ===== MT5 =====
def iniciar():
    login, ruta = os.environ.get('MT5_LOGIN', '').strip(), os.environ.get('MT5_PATH', '').strip()
    kw = dict(login=int(login), password=os.environ.get('MT5_PASSWORD', ''), server=os.environ.get('MT5_SERVER', '').strip(),
              timeout=180000) if login else {}
    return mt5.initialize(ruta, **kw) if ruta else mt5.initialize(**kw)


def _terminal_ok():
    ti = getattr(mt5, 'terminal_info', None)
    if ti is None:
        return True
    t = ti()
    return t is not None and bool(getattr(t, 'connected', True))


def conectado():
    if mt5.account_info() is not None and _terminal_ok():      # account_info puede venir de caché con el terminal desconectado
        return True
    for _ in range(3):
        mt5.shutdown(); time.sleep(3)
        if iniciar() and mt5.account_info() is not None and _terminal_ok():
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
    ahora = ahora_ny()
    abierto = (ahora.weekday() < 5 and T('09:30') <= ahora.time() < T('16:00')     # con mercado cerrado el último tick puede ser viejo
               and str(ahora.date()) not in FERIADOS)
    srv_menos_utc = round((t.time - time.time()) / 3600) * 3600 if (t and t.time and abierto) else None
    ny_menos_utc = int(dt.datetime.now(NY).utcoffset().total_seconds())
    DESFASE = 7 * 3600
    if srv_menos_utc is not None and abs(srv_menos_utc - ny_menos_utc - DESFASE) > 3 * 3600:
        log('aviso', detalle=f'hora del servidor rara ({srv_menos_utc / 3600:+.0f} h vs UTC; tick viejo?): uso +7 h sobre Nueva York')
        srv_menos_utc = None
    if srv_menos_utc is not None and srv_menos_utc - ny_menos_utc != DESFASE:
        DESFASE = srv_menos_utc - ny_menos_utc
        log('aviso', detalle=f'el servidor no va 7 h adelante de Nueva York: uso {DESFASE / 3600:+.1f} h')


def a_ny(t_servidor):
    if TZ_SERVIDOR is not None:      # servidor con su propio horario de verano: convierte vela por vela
        local = dt.datetime(1970, 1, 1) + dt.timedelta(seconds=int(t_servidor))
        return local.replace(tzinfo=TZ_SERVIDOR).astimezone(NY).replace(tzinfo=None)
    return dt.datetime(1970, 1, 1) + dt.timedelta(seconds=int(t_servidor) - DESFASE)


def velas(sym):
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 9000)
    if r is None or len(r) == 0:
        return None
    df = pd.DataFrame(r)
    df.index = [a_ny(x) for x in df['time']]
    df = df.rename(columns={'open': 'o', 'high': 'h', 'low': 'l', 'close': 'c', 'tick_volume': 'v'})[['o', 'h', 'l', 'c', 'v']]
    df = df[~df.index.duplicated(keep='last')]
    return df[(df.index.time >= T('09:30')) & (df.index.time < T('16:00'))]


def _en_rejilla(g, d, hasta=None):
    """Las velas del día en su lugar (9:30, 9:35, …): si falta una, se rellena con el último cierre, como la simulación."""
    idx = pd.date_range(dt.datetime.combine(d, T('09:30')), dt.datetime.combine(d, T('15:55')), freq='5min')
    if hasta is not None:
        idx = idx[idx <= hasta]
    if len(g) == len(idx) and (g.index == idx).all():
        return g
    r = g.reindex(idx)
    c = r['c'].ffill().bfill()
    for col in ('o', 'h', 'l'):
        r[col] = r[col].fillna(c)
    r['c'], r['v'] = c, r['v'].fillna(0)
    return r


def partir_dias(df, hoy):
    dias = {d: g for d, g in df.groupby(df.index.date)}
    previos = [_en_rejilla(g, d) for d, g in sorted(dias.items()) if d < hoy and str(d) not in FERIADOS and len(g) >= VELAS_DIA_MIN]
    h = dias.get(hoy, df.iloc[0:0])
    if len(h) and h.index[0].time() <= T('09:35'):      # sin la apertura no se rellena: sincronizar() no opera (AUDIT_010 A2)
        h = _en_rejilla(h, hoy, h.index.max())
    return h, previos


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
            log('aviso', detalle=f'no pude calcular la volatilidad ({e}); uso {CONTRATOS:g} MNQ')
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
        if 'cot' in CAPAS_SOMBRA:
            log('sombra', detalle=f'fondos apalancados recortaron fuerte (COT): sería ×{COT_RECORTE:g}; en sombra, no cambia el tamaño')
        else:
            f *= COT_RECORTE; mot.append('fondos apalancados recortaron fuerte (COT)')
    return f, bool(m.get('empleo_nfp')), mot


class EstadoDanado(Exception):
    pass


def leer_estado(estricto=False):
    """Estado del bot. Sin archivo: {}. Archivo dañado: {} (o EstadoDanado con estricto=True, para no operar a ciegas)."""
    if not os.path.exists(ESTADO):
        return {}
    try:
        with open(ESTADO, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception as e:
        if estricto:
            raise EstadoDanado(str(e))
        return {}


def guardar_estado(e):
    tmp = ESTADO + '.tmp'
    with _ARCHIVOS:
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(e, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, ESTADO)
    marcar_subida()


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


def _lotes_directos(x, info):
    """Lotes = x redondeado al paso del símbolo, respetando el mínimo y el máximo; 0 si redondea a 0 (ese día no opera)."""
    paso = info.volume_step or 0.01
    lt = round(round(x / paso) * paso, 8)
    if lt <= 0:
        return 0.0
    lt = max(lt, getattr(info, 'volume_min', 0.0) or 0.0)
    vmax = getattr(info, 'volume_max', None)
    return min(lt, float(vmax)) if vmax else lt


def lotes_del_dia(info, f_orb, f_ruido):
    """MNQ y lotes de hoy por estrategia. 100K con MNQ enteros: exactamente el cálculo de siempre (MNQ enteros; puede dar 0, igual que
    la simulación). Otro capital (50K: BOT_MNQ 3 / 2) o MNQ fraccional: lotes directos = lotes por MNQ × MNQ × capas, al paso del símbolo."""
    paso, lpm = info.volume_step or 0.01, lotes_por_mnq(info)
    if FTMO_INICIAL == 100000 and CONTRATOS.is_integer():
        n_mnq, n_ruido = round(CONTRATOS * f_orb), round(CONTRATOS * f_ruido)
        return (n_mnq, n_ruido) + tuple(round(round(lpm * n / paso) * paso, 8) for n in (n_mnq, n_ruido))
    n_mnq, n_ruido = CONTRATOS * f_orb, CONTRATOS * f_ruido
    return (n_mnq, n_ruido) + tuple(_lotes_directos(lpm * n, info) for n in (n_mnq, n_ruido))


def lotes_relleno(info):
    """Tamaño de los días de relleno (meta lograda antes de los 4 días): 1 MNQ en 100K (2 lotes), 0.5 MNQ en 50K (1 lote)."""
    paso = info.volume_step or 0.01
    lt = round(round(lotes_por_mnq(info) * ESCALA_FTMO / paso) * paso, 8)
    lt = max(lt, getattr(info, 'volume_min', 0.0) or paso)        # AUDIT_012 A1: nunca 0 ni debajo del mínimo (100K: sin cambios)
    vmax = getattr(info, 'volume_max', None)
    return min(lt, float(vmax)) if vmax else lt


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
    ds = mt5.history_deals_get(desde, dt.datetime.now(UTC) + dt.timedelta(days=1))
    if ds is not None and any(d.magic == MAGIC[clave] and d.entry == mt5.DEAL_ENTRY_IN and a_ny(d.time).date() == hoy for d in ds):
        return True
    return entrada_anotada(clave, hoy)


_SALIDA_PROT = {}     # salidas que hizo el bot por protección (escalera, stop de seguridad): esperan al siguiente chequeo


_MOTIVOS_PROT = ('stop de seguridad:', 'el precio ya está en el piso asegurado')


def cargar_salidas_prot(hoy):
    """AUDIT_010 A5: al arrancar (relevo de las 12:50 o relanzamiento del vigía) recupera de la bitácora las salidas por
    protección de hoy, para que la zona de ruido espere al siguiente chequeo igual que si el proceso no se hubiera reiniciado."""
    por_nombre = {v: k for k, v in NOMBRE.items()}
    try:
        with _ARCHIVOS, open(BITACORA, newline='', encoding='utf-8') as fh:
            filas = list(csv.DictReader(fh))
    except Exception:
        return
    for r in filas:
        clave = por_nombre.get(r.get('estrategia') or '')
        if clave is None or r.get('evento') != 'salida' or not (r.get('detalle') or '').startswith(_MOTIVOS_PROT):
            continue
        try:
            t = dt.datetime.strptime(r['hora_UTC'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC).astimezone(NY).replace(tzinfo=None)
        except (KeyError, ValueError):
            continue
        if t.date() == hoy and (_SALIDA_PROT.get(clave) is None or t > _SALIDA_PROT[clave]):
            _SALIDA_PROT[clave] = t


def salio_por_stop(clave, desde_ny):
    """¿Salió esta estrategia por stop (del servidor o de protección del bot) después del último chequeo?"""
    if desde_ny is None:
        return False
    if _SALIDA_PROT.get(clave) is not None and _SALIDA_PROT[clave] >= desde_ny:
        return True
    ds = mt5.history_deals_get(dt.datetime.now(UTC) - dt.timedelta(days=2), dt.datetime.now(UTC) + dt.timedelta(days=1)) or []
    return any(d.magic == MAGIC[clave] and d.entry == mt5.DEAL_ENTRY_OUT and d.reason == mt5.DEAL_REASON_SL
               and a_ny(d.time) >= desde_ny for d in ds)


_AVISO_MARGEN = {}


def log_cada(clave_aviso, *a, cada=300, **k):
    """Igual que log(), pero el mismo aviso como máximo una vez cada `cada` segundos (no llena la bitácora cada 2 s)."""
    ahora_m = time.time()
    if ahora_m - _AVISO_MARGEN.get(clave_aviso, 0) >= cada:
        _AVISO_MARGEN[clave_aviso] = ahora_m
        log(*a, **k)


def _usd_punto_lote(info):
    return info.trade_tick_value / info.trade_tick_size if info.trade_tick_size else 1.0


def _lotes_por_margen(sym, lado, lotes, precio, clave, reserva=MARGEN_RESERVA):
    """Recorta los lotes de una ENTRADA NUEVA si no cabe en el margen libre (nunca se usa al cerrar).
    Revisa el margen real del bróker y, en modo FTMO, también el de FTMO Swing (1:15 sobre la cuenta virtual de 100K),
    para que el ensayo en Tickmill recorte exactamente cuando lo haría FTMO. Aparta el margen que necesitarían las
    órdenes pendientes de la otra estrategia (si se llenan después, no deben quedarse sin margen)."""
    acc, info = mt5.account_info(), mt5.symbol_info(sym)
    if acc is None or info is None or precio is None or precio <= 0 or lotes <= 0:
        return lotes
    upl = _usd_punto_lote(info)
    otras = [o for o in (mt5.orders_get(symbol=sym) or []) if o.magic in MAGIC.values() and o.magic != MAGIC[clave]]
    lotes_apartados = sum(max([o.volume_current for o in otras if o.magic == m] or [0.0]) for m in set(o.magic for o in otras))
    limites = []
    calc = getattr(mt5, 'order_calc_margin', None)
    if calc is not None:
        try:
            m1 = calc(mt5.ORDER_TYPE_BUY if lado > 0 else mt5.ORDER_TYPE_SELL, sym, 1.0, float(precio))
        except Exception:
            m1 = None
        if m1 and m1 > 0:
            limites.append((float(acc.margin_free) - lotes_apartados * m1, m1, 'bróker'))
    if MODO == 'ftmo':
        m1 = precio * upl / FTMO_APALANCAMIENTO
        f = (leer_estado().get('ftmo') or {})
        eq_v = FTMO_INICIAL + acc.equity - f.get('base', acc.equity) if CUENTA != 'ftmo' else acc.equity
        usado = sum(p.volume * (p.price_current or p.price_open) * upl / FTMO_APALANCAMIENTO
                    for p in (mt5.positions_get(symbol=sym) or []) if p.magic in MAGIC.values())
        limites.append((eq_v - usado - lotes_apartados * m1, m1, f'FTMO 1:{FTMO_APALANCAMIENTO:g}'))
    if not limites:
        return lotes
    paso = info.volume_step or 0.01
    maximo, libre, quien = min((math.floor(max(0.0, li * reserva) / m1 / paso + 1e-9) * paso, li, q) for li, m1, q in limites)
    maximo = round(maximo, 8)
    if lotes <= maximo:
        return lotes
    if maximo < (info.volume_min or paso):
        ahora_m = time.time()
        if ahora_m - _AVISO_MARGEN.get(clave, 0) >= 300:
            _AVISO_MARGEN[clave] = ahora_m
            log('aviso', NOMBRE[clave], detalle=f'margen libre insuficiente ({quien}: ${libre:,.0f}): no abro {lotes:g} lotes')
        return 0.0
    log('tamaño', NOMBRE[clave], detalle=f'recorte por margen libre ({quien}: ${libre:,.0f}): {lotes:g} → {maximo:g} lotes')
    return maximo


def lotes_por_margen(sym, lado, lotes, precio, clave, reserva=MARGEN_RESERVA):
    try:
        return _lotes_por_margen(sym, lado, lotes, precio, clave, reserva)
    except Exception as ex:                       # un fallo al revisar el margen no debe tumbar la entrada: el bróker decide
        log('aviso', NOMBRE[clave], detalle=f'no pude revisar el margen ({ex}): mando {lotes:g} lotes')
        return lotes


def margen_ftmo(sym=None, lotes_extra=0.0, solo_realizado=False):
    """US$ que la cuenta puede perder antes del freno FTMO (piso del día + colchón proyectado con `lotes_extra`). None si no aplica.
    solo_realizado=True: medido sobre el balance (pérdidas ya cerradas), para el stop de cada posición: así una caída temporal
    de la otra posición no acerca stops para siempre. Para permitir entradas se usa lo menor entre balance y equity."""
    if MODO != 'ftmo':
        return None
    try:
        acc, d = mt5.account_info(), (leer_estado().get('dia') or {})
        if acc is None or 'piso' not in d:
            return None
        col = colchon_freno(sym, lotes_extra) if sym else FTMO_FRENO * FTMO_INICIAL
        base = acc.balance if solo_realizado else min(acc.balance, acc.equity)
        return base - (d['piso'] + col)
    except Exception:
        return None


def _rejilla(info):
    """Paso de precio válido: trade_tick_size si las cotizaciones caen en esa rejilla; si no, point."""
    pt = getattr(info, 'point', 0) or 0.01
    ts = getattr(info, 'trade_tick_size', 0) or 0
    if ts <= pt:
        return pt
    bid = getattr(info, 'bid', None)
    if isinstance(bid, (int, float)) and bid > 0 and abs(bid / ts - round(bid / ts)) > 1e-6:
        return pt                                    # el bróker cotiza fuera de esa rejilla: el tick_size es solo para el valor en US$
    return ts


def alinear(info, x, hacia_arriba):
    """Precio en la rejilla de ticks válida del símbolo."""
    return round(_a_tick(x, _rejilla(info), hacia_arriba), info.digits)


def _a_tick(x, ts, hacia_arriba):
    n = x / ts
    k = round(n)
    n = k if abs(n - k) < 1e-6 else (math.ceil(n) if hacia_arriba else math.floor(n))
    return n * ts


def _stop_por_usd(info, lado, lotes, precio, usd):
    """Stop a US$ `usd` de `precio` para `lotes`, alineado al tick y redondeado hacia el precio (nunca arriesga más). None si faltan datos."""
    tv, ts = getattr(info, 'trade_tick_value', 0) or 0, getattr(info, 'trade_tick_size', 0) or 0
    if tv <= 0 or ts <= 0 or lotes <= 0 or precio <= 0 or lado not in (1, -1):
        return None
    d = max(0.0, usd) / (lotes * tv / ts)
    g = _rejilla(info)
    return round(_a_tick(precio - d, g, True) if lado > 0 else _a_tick(precio + d, g, False), info.digits)


def riesgo_abierto(sym, excluir=None, antes_de=None):
    """US$ que perderían las posiciones abiertas (de otras estrategias) si tocan su stop, medido desde su entrada.
    Con el stop en break even o mejor, su riesgo es 0. antes_de=(time, ticket): solo las que entraron antes."""
    info = mt5.symbol_info(sym)
    if info is None:
        return 0.0
    upl, tot = _usd_punto_lote(info), 0.0
    for clave in MAGIC:
        if clave == excluir:
            continue
        for p in posicion(sym, clave)[1]:
            if antes_de is not None and (p.time, p.ticket) >= antes_de:
                continue
            lado = 1 if p.type == mt5.POSITION_TYPE_BUY else -1
            tot += (max(0.0, (p.price_open - p.sl) * lado) * p.volume * upl) if p.sl else (TOPE_POSICION_USD or 0.0)
    return tot


def riesgo_despues(sym, excluir, desde=None):
    """US$ que arriesgan las otras estrategias con lo que entró DESPUÉS de `desde`=(time, ticket) (desde=None: ninguna posición)
    más su orden pendiente de mayor riesgo (de un par OCO solo se llena una). Con el stop en break even o mejor, su riesgo es 0."""
    info = mt5.symbol_info(sym)
    if info is None:
        return 0.0
    upl, tot = _usd_punto_lote(info), 0.0
    for clave in MAGIC:
        if clave == excluir:
            continue
        if desde is not None:
            for p in posicion(sym, clave)[1]:
                if (p.time, p.ticket) > desde:
                    lado = 1 if p.type == mt5.POSITION_TYPE_BUY else -1
                    tot += (max(0.0, (p.price_open - p.sl) * lado) * p.volume * upl) if p.sl else (TOPE_POSICION_USD or 0.0)
        pend = [(max(0.0, (o.price_open - o.sl) * (1 if o.type == mt5.ORDER_TYPE_BUY_STOP else -1)) * o.volume_current * upl)
                if getattr(o, 'sl', 0) else (TOPE_POSICION_USD or 0.0) for o in pendientes(sym, clave)]
        tot += max(pend, default=0.0)
    return tot


def lotes_pendientes_otras(sym, excluir):
    """AUDIT_011 A1: lotes de la mayor orden pendiente de las otras estrategias (para proyectar el colchón del freno si se llena)."""
    return max([o.volume_current for c in MAGIC if c != excluir for o in pendientes(sym, c)], default=0.0)


def _reserva(usd, m, riesgo_desp):
    """AUDIT_010 A1: la que entró antes deja reservado para la de después lo que esta arriesga (máx. $500, el piso de C1),
    así las dos juntas nunca pasan del margen antes del freno, ni con el bot caído. 8 años: −1.3% vs −1.7% del C1 anterior."""
    if m is None or riesgo_desp <= 0:
        return usd
    return min(usd, m - min(riesgo_desp, TOPE_MIN_USD))


def _tope_compartido(base, m, riesgo_otras):
    """C1: la posición que entra después recibe lo que deja la que ya estaba (mínimo $500, nunca deja de entrar por esto).
    Con _reserva (la de antes deja $500), las dos juntas no pasan del margen antes del freno ni con el bot caído."""
    if m is None:
        return base
    return min(base, max(TOPE_MIN_USD, m - riesgo_otras))


def tope_stop(sym, lado, lotes, precio, sl, usd=None, clave=None):
    """Stop de seguridad al ENTRAR: la posición no puede perder más de min($4,500, margen antes del freno FTMO) si el bot se cae.
    Devuelve (stop, topado). Stop None = no hay margen para abrir. Datos del símbolo inválidos = deja el stop de la estrategia.
    Medido en 8 años: salta en ~1–3% de las operaciones y no cambia el resultado (+$0.06/día ruido, −$1.8 por operación ORB)."""
    if TOPE_POSICION_USD is None or not TOPE_POSICION_USD or TOPE_POSICION_USD <= 0 or sl is None:
        return sl, False
    info = mt5.symbol_info(sym)
    if info is None or lado not in (1, -1) or not lotes or lotes <= 0 or not precio or precio <= 0:
        return sl, False
    if usd is None:
        m = margen_ftmo(sym, lotes)                                   # para entrar: lo menor entre balance y equity
        usd = TOPE_POSICION_USD if m is None else min(TOPE_POSICION_USD, m)
        if usd >= TOPE_MIN_USD:
            m_r = margen_ftmo(sym, lotes, solo_realizado=True)        # para repartir: lo realizado (el flotante ya está en riesgo_abierto)
            base_r = TOPE_POSICION_USD if m_r is None else min(TOPE_POSICION_USD, m_r)
            usd = min(usd, _tope_compartido(base_r, m_r, riesgo_abierto(sym, excluir=clave)))
            lp = lotes_pendientes_otras(sym, clave)                   # pendientes de la otra estrategia: les deja su parte,
            m_res = m_r if not lp else margen_ftmo(sym, lotes + lp, solo_realizado=True)   # con el colchón de cuando se llenen
            usd = _reserva(usd, m_res, riesgo_despues(sym, clave))
    if usd < TOPE_MIN_USD:
        return None, True
    nuevo = _stop_por_usd(info, lado, lotes, precio, usd)
    if nuevo is None or (lado > 0 and nuevo <= sl) or (lado < 0 and nuevo >= sl):
        return sl, False
    if (lado > 0 and nuevo >= precio) or (lado < 0 and nuevo <= precio):
        return None, True
    return nuevo, True


def asegurar_tope(sym):
    """Cada ciclo y tras cada llenado. Cada posición y cada orden pendiente: pérdida desde su entrada ≤ min($4,500, margen ya realizado
    antes del freno FTMO). Corrige el deslizamiento y, tras pérdidas cerradas del día (o una re-entrada), acerca los stops para que,
    si el bot se cae, nada cruce el límite. Con el bot vivo salta cuando lo haría el freno (no mira el flotante de la otra posición).
    Solo acerca stops, nunca los aleja. Si ya no hay margen, cierra posiciones y cancela pendientes."""
    if TOPE_POSICION_USD is None:
        return
    info, t = mt5.symbol_info(sym), mt5.symbol_info_tick(sym)
    if info is None or t is None or t.bid <= 0 or t.ask <= 0:
        return
    m = margen_ftmo(sym, solo_realizado=True)
    usd = TOPE_POSICION_USD if m is None else min(TOPE_POSICION_USD, m)
    pt = info.point or 0.01
    minimo = max((info.trade_stops_level or 0) * pt, pt)
    paso = max(1.0, 5 * _rejilla(info))
    txt = f'máx ${TOPE_POSICION_USD:,.0f} desde la entrada' + (f'; margen realizado antes del freno ${m:,.0f}' if m is not None else '')
    for clave in MAGIC:
        _, ps = posicion(sym, clave)
        for p in ps:
            lado = 1 if p.type == mt5.POSITION_TYPE_BUY else -1
            actual = t.bid if lado > 0 else t.ask
            usd_p = usd if usd < TOPE_MIN_USD else _tope_compartido(usd, m, riesgo_abierto(sym, excluir=clave, antes_de=(p.time, p.ticket)))
            if usd >= TOPE_MIN_USD:
                lp = lotes_pendientes_otras(sym, clave)
                m_res = m if not lp else margen_ftmo(sym, lp, solo_realizado=True)
                usd_p = _reserva(usd_p, m_res, riesgo_despues(sym, clave, (p.time, p.ticket)))
            nuevo = _stop_por_usd(info, lado, p.volume, p.price_open, usd_p)
            if nuevo is None:
                continue
            sl = p.sl if p.sl else (-1e18 if lado > 0 else 1e18)
            if (nuevo - sl) * lado <= 0:
                continue                                       # el stop actual ya es igual o más cercano
            if usd < TOPE_MIN_USD or (lado > 0 and nuevo >= actual - minimo) or (lado < 0 and nuevo <= actual + minimo):
                if cerrar(sym, clave, f'stop de seguridad: sin margen antes del límite FTMO ({txt})'):
                    _SALIDA_PROT[clave] = ahora_ny()
                continue
            if (nuevo - sl) * lado < paso:
                continue                                       # mejora mínima: no gasta solicitudes
            r = mt5.order_send(dict(action=mt5.TRADE_ACTION_SLTP, symbol=sym, position=p.ticket, sl=nuevo, tp=p.tp or 0.0, magic=MAGIC[clave]))
            if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
                log('protege', NOMBRE[clave], 'compra' if lado > 0 else 'venta', p.volume, f'{nuevo:.2f}',
                    f'stop de seguridad ({txt}) · stop de {p.sl:.2f} a {nuevo:.2f} · posición {p.ticket}')
            else:
                log('error', NOMBRE[clave], detalle=f"no pude poner el stop de seguridad: {r.retcode if r else mt5.last_error()} {r.comment if r else ''}")
        for o in pendientes(sym, clave):
            lado = 1 if o.type == mt5.ORDER_TYPE_BUY_STOP else -1
            m_o = margen_ftmo(sym, o.volume_current)                         # para entrar: lo menor entre balance y equity, colchón con su volumen
            m_r = margen_ftmo(sym, o.volume_current, solo_realizado=True)    # para su stop: lo realizado
            usd_o = TOPE_POSICION_USD if m_r is None else min(TOPE_POSICION_USD, m_r)
            if usd_o >= TOPE_MIN_USD:
                usd_o = _tope_compartido(usd_o, m_r, riesgo_abierto(sym, excluir=clave))
            nuevo = _stop_por_usd(info, lado, o.volume_current, o.price_open, usd_o)
            mas_cerca = nuevo is not None and (not o.sl or (nuevo - o.sl) * lado > 0)          # solo importa si el tope acercaría el stop
            sin_espacio = mas_cerca and ((lado > 0 and o.price_open - nuevo <= minimo) or (lado < 0 and nuevo - o.price_open <= minimo))
            if (m_o is not None and m_o < TOPE_MIN_USD) or usd_o < TOPE_MIN_USD or sin_espacio:
                r = mt5.order_send(dict(action=mt5.TRADE_ACTION_REMOVE, order=o.ticket))
                if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
                    log('cancela', NOMBRE[clave], 'compra' if lado > 0 else 'venta', o.volume_current, f'{o.price_open:.2f}',
                        ('orden pendiente cancelada: su stop de seguridad quedaría pegado al precio (distancia mínima del bróker)' if sin_espacio and not
                         ((m_o is not None and m_o < TOPE_MIN_USD) or usd_o < TOPE_MIN_USD) else
                         f'orden pendiente cancelada: sin margen antes del límite FTMO (margen al llenarse ${(m_o if m_o is not None else usd_o):,.0f})')
                        + f' · orden {o.ticket}')
                else:
                    log('error', NOMBRE[clave], detalle=f"no pude cancelar la pendiente {o.ticket} sin margen: {r.retcode if r else mt5.last_error()}")
                continue
            sl = o.sl if o.sl else (-1e18 if lado > 0 else 1e18)
            if nuevo is None or (nuevo - sl) * lado < paso:
                continue
            r = mt5.order_send(dict(action=mt5.TRADE_ACTION_MODIFY, order=o.ticket, symbol=sym, price=o.price_open, sl=nuevo,
                                    tp=getattr(o, 'tp', 0.0) or 0.0, type_time=getattr(o, 'type_time', mt5.ORDER_TIME_GTC),
                                    expiration=getattr(o, 'time_expiration', 0) or 0))
            if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
                log('protege', NOMBRE[clave], 'compra' if lado > 0 else 'venta', o.volume_current, f'{nuevo:.2f}',
                    f'stop de seguridad en la orden pendiente (máx ${usd_o:,.0f} desde su precio) · stop de {o.sl:.2f} a {nuevo:.2f} · orden {o.ticket}')
            else:
                log('error', NOMBRE[clave], detalle=f"no pude acercar el stop de la pendiente {o.ticket}: {r.retcode if r else mt5.last_error()}")


def enviar(sym, lado, lotes, clave, ticket=None, sl=None):
    t, info = mt5.symbol_info_tick(sym), mt5.symbol_info(sym)
    if t is None or info is None or t.bid <= 0 or t.ask <= 0:
        log('error', NOMBRE[clave], detalle=f'sin precio ({mt5.last_error()})'); return None
    precio = t.ask if lado > 0 else t.bid
    pt = info.point or 0.01
    req = dict(action=mt5.TRADE_ACTION_DEAL, symbol=sym, volume=float(lotes), price=precio, magic=MAGIC[clave],
               type=mt5.ORDER_TYPE_BUY if lado > 0 else mt5.ORDER_TYPE_SELL, deviation=max(20, int(precio * 0.001 / pt)),
               comment=clave, type_time=mt5.ORDER_TIME_GTC)
    if ticket is not None:
        req['position'] = ticket
    else:                                                    # apertura: SIEMPRE con stop válido; si no, no se manda
        cierre_px = t.bid if lado > 0 else t.ask             # el stop se mide contra el precio al que se cerraría
        minimo = max((info.trade_stops_level or 0) * pt, pt)
        if sl is not None:
            sl0, sl = sl, alinear(info, sl, lado > 0)            # en la rejilla de ticks, hacia el precio (nunca arriesga de más)
            if (lado > 0 and sl >= cierre_px - minimo) or (lado < 0 and sl <= cierre_px + minimo):
                sl = alinear(info, sl0, lado < 0)                # si así queda pegado al precio, un tick hacia afuera
        if sl is None or (lado > 0 and sl >= cierre_px - minimo) or (lado < 0 and sl <= cierre_px + minimo):
            log('error', NOMBRE[clave], 'compra' if lado > 0 else 'venta', lotes,
                detalle=f'no abro: stop {sl} inválido (precio {cierre_px:.2f}, distancia mínima {minimo:g}); nunca se abre sin stop')
            return None
        req['sl'] = sl
    enviar.sl_enviado = req.get('sl')
    r = None
    for f in FILL:
        r = mt5.order_send({**req, 'type_filling': f})
        if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
            enviar.ultimo = r
            return r.price or precio
        if r is None or r.retcode != 10030:
            break
    log('error', NOMBRE[clave], 'compra' if lado > 0 else 'venta', lotes,
        detalle=f"orden rechazada: {r.retcode if r else mt5.last_error()} {r.comment if r else ''}")
    return None


def pendientes(sym, clave):
    return [o for o in (mt5.orders_get(symbol=sym) or []) if o.magic == MAGIC[clave]]


def plano(sym, clave=None):
    """True solo si MT5 confirma que no hay posiciones ni pendientes del bot (un None de MT5 es error, no «vacío»)."""
    ps, os_ = mt5.positions_get(symbol=sym), mt5.orders_get(symbol=sym)
    if ps is None or os_ is None or not _terminal_ok():
        return False
    mags = set(MAGIC.values()) if clave is None else {MAGIC[clave]}
    return not any(x.magic in mags for x in list(ps) + list(os_))


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
    if info is None:
        log('error', NOMBRE[clave], detalle=f'sin info del símbolo para orden pendiente ({mt5.last_error()})')
        return False
    lotes = lotes_por_margen(sym, lado, lotes, precio, clave)
    if lotes <= 0:
        return False
    if sl is None:
        log('error', NOMBRE[clave], detalle='orden pendiente sin stop: no la pongo'); return False
    precio = alinear(info, precio, lado > 0)              # compra arriba / venta abajo del rango, en la rejilla de ticks
    sl_t, topado = tope_stop(sym, lado, lotes, precio, sl, clave=clave)
    if sl_t is None:
        log_cada(('sin_margen_pend', clave), 'aviso', NOMBRE[clave], detalle='sin margen antes del freno FTMO para el stop de seguridad: no pongo la orden'); return False
    if topado:
        motivo += f' · stop de seguridad a ${abs(precio - sl_t) * lotes * _usd_punto_lote(info):,.0f}'
    sl = alinear(info, sl_t, lado > 0)                    # hacia el precio
    pt = info.point or 0.01
    minimo = max((info.trade_stops_level or 0) * pt, pt)
    if (lado > 0 and precio - sl <= minimo) or (lado < 0 and sl - precio <= minimo):
        log_cada(('stop_cerca', clave), 'error', NOMBRE[clave], detalle=f'stop {sl} demasiado cerca de la orden ({precio:.2f}, mínimo {minimo:g}): no la pongo'); return False
    req = dict(action=mt5.TRADE_ACTION_PENDING, symbol=sym, volume=float(lotes), price=precio,
               sl=sl, magic=MAGIC[clave], comment=clave,
               type=mt5.ORDER_TYPE_BUY_STOP if lado > 0 else mt5.ORDER_TYPE_SELL_STOP)
    r = None
    for tt in (mt5.ORDER_TIME_DAY, mt5.ORDER_TIME_GTC):
        for f in (mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK):
            r = mt5.order_send({**req, 'type_time': tt, 'type_filling': f})
            if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
                log('pendiente', NOMBRE[clave], 'compra' if lado > 0 else 'venta', lotes, f'{precio:.2f}', f'{motivo} · stop {sl:,.2f} · orden {getattr(r, "order", "")}')
                return True
            if r is None or r.retcode not in (10030, 10022):   # solo reintenta otro filling/expiración si el broker rechazó ese tipo
                break
        if r is None or r.retcode not in (10030, 10022):
            break
    log('error', NOMBRE[clave], detalle=f"no pude poner la orden pendiente: {r.retcode if r else mt5.last_error()} {r.comment if r else ''}")
    return False


def _fecha_ny_log(hora_utc_txt):
    try:
        return dt.datetime.strptime(hora_utc_txt, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC).astimezone(NY).date()
    except Exception:
        return None


def entrada_anotada(clave, hoy):
    try:
        with open(BITACORA, encoding='utf-8') as fh:
            return any(f['evento'] == 'entrada' and f['estrategia'] == NOMBRE[clave] and _fecha_ny_log(f['hora_UTC']) == hoy
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
            info = mt5.symbol_info(sym)
            mult = (info.trade_tick_value / info.trade_tick_size) if (info and info.trade_tick_size) else 1.0
            res = (px - p.price_open) * (-lado) * p.volume * mult
            log('salida', NOMBRE[clave], 'venta' if lado < 0 else 'compra', p.volume, f'{px:.2f}',
                f'{motivo} · entró a {p.price_open:.2f} · resultado aprox. {res:+,.2f} USD · posición {p.ticket}')
    return plano(sym, clave)


def colchon_freno(sym, lotes_extra=0.0):
    """Distancia al límite FTMO a la que se cierra todo: 0.4% del capital o 30 pts × $/pt abierto (lo mayor)."""
    base = FTMO_FRENO * FTMO_INICIAL
    try:
        info = mt5.symbol_info(sym)
        upl = _usd_punto_lote(info) if info is not None else 0.0
        vol = sum(p.volume for c in MAGIC for p in posicion(sym, c)[1]) + (lotes_extra or 0.0)
        return max(base, COLCHON_PTS * vol * upl)
    except Exception:
        return base


def cerrar_todo(sym, motivo, intentos=1):
    """Cierra ambas estrategias y confirma que no quede nada abierto. True = plano."""
    for k in range(intentos):
        planas = [cerrar(sym, clave, motivo) for clave in MAGIC]
        if all(planas):
            return True
        if k < intentos - 1:
            time.sleep(2)
    log('error', detalle=f'quedan posiciones u órdenes abiertas tras intentar cerrar ({motivo}); reintento')
    return False


def abrir(sym, clave, lado, lotes, sl, motivo, ref=None):
    t = mt5.symbol_info_tick(sym)
    if t is None or t.bid <= 0 or t.ask <= 0:
        log('error', NOMBRE[clave], detalle=f'sin precio para entrar ({mt5.last_error()}): no abro'); return
    px_ref = t.ask if lado > 0 else t.bid
    lotes = lotes_por_margen(sym, lado, lotes, px_ref, clave)
    if lotes <= 0:
        return
    sl_t, topado = tope_stop(sym, lado, lotes, px_ref, sl, clave=clave)
    if sl_t is None:
        log_cada(('sin_margen_abrir', clave), 'aviso', NOMBRE[clave], detalle='sin margen antes del freno FTMO para el stop de seguridad: no abro'); return
    if topado:
        motivo += ' · stop de seguridad'
    sl = sl_t
    px = enviar(sym, lado, lotes, clave, sl=sl)
    if px is not None:
        log('entrada', NOMBRE[clave], 'compra' if lado > 0 else 'venta', lotes, f'{px:.2f}',
            motivo + f' · stop {getattr(enviar, "sl_enviado", None) or sl:,.2f} · deslizamiento {(px - px_ref) * lado:+.2f} pts'
            + (f' · vs cierre del chequeo {ref:,.2f}: {(px - ref) * lado:+.2f} pts' if ref else '')
            + f' · orden {getattr(getattr(enviar, "ultimo", None), "order", "")}')
        asegurar_tope(sym)                         # corrige el stop si el llenado fue peor que el precio pedido


# ===== Lógica del día =====
def caida_ayer(previos):
    """Retorno cierre a cierre de ayer (horario normal). None si faltan días."""
    if len(previos) < 2:
        return None
    return float(previos[-1].c.iloc[-1]) / float(previos[-2].c.iloc[-1]) - 1


def sincronizar(sym, df, hoy, ahora, lotes, cierre=CIERRE):
    if not isinstance(lotes, dict):
        lotes = {'orb': lotes, 'ruido': lotes}
    if mt5.positions_get(symbol=sym) is None or mt5.orders_get(symbol=sym) is None or not _terminal_ok():
        return                                     # MT5 no respondió: no se decide nada a ciegas (evita duplicados)
    hoy_df, previos = partir_dias(df, hoy)
    if len(hoy_df) == 0 or hoy_df.index[0].time() > T('09:35'):
        return
    r1 = caida_ayer(previos)
    sin_orb = r1 is not None and r1 < CAIDA_ORB
    sin_ruido = r1 is not None and r1 < CAIDA_RUIDO
    # 0 MNQ (las capas de tamaño dan menos de 0.5): esa estrategia no ABRE hoy, pero sigue administrando lo que ya esté abierto
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
                    f'se llenó la orden pendiente del rango de 30 min ({lo:,.2f}–{hi:,.2f}) · deslizamiento {(p.price_open - nivel) * lado_r:+.2f} pts · stop {p.sl:,.2f} · posición {p.ticket}')
                asegurar_tope(sym)
            if est == 'stop' or (lado_m != 0 and lado_m != lado_r):
                cerrar(sym, 'orb', 'tocó el stop del rango de 30 min')
        elif opero_hoy('orb', hoy) or est in ('stop', 'ambos') or ahora.time() >= cierre:
            if pend:
                cancelar_pendientes(sym, 'orb', 'el rango ya se operó o ya no aplica hoy')
        elif est == 'esperando':
            tiene_buy = any(o.type == mt5.ORDER_TYPE_BUY_STOP for o in pend)
            tiene_sell = any(o.type == mt5.ORDER_TYPE_SELL_STOP for o in pend)
            if not (tiene_buy and tiene_sell) and lotes['orb'] > 0:
                info, t = mt5.symbol_info(sym), mt5.symbol_info_tick(sym)
                if info is not None and t is not None:
                    pt = info.point or 0.01
                    dist = max(pt, (info.trade_stops_level or 0) * pt)
                    rango = f'rango de 30 min ({lo:,.2f}–{hi:,.2f})'
                    if not tiene_buy and t.ask + dist < hi + pt:
                        poner_pendiente(sym, 'orb', 1, lotes['orb'], hi + pt, lo, 'compra si rompe arriba del ' + rango)
                    if not tiene_sell and t.bid - dist > lo - pt:
                        poner_pendiente(sym, 'orb', -1, lotes['orb'], lo - pt, hi, 'venta si rompe abajo del ' + rango)
        elif est == 'activo':
            ya_dentro = False
            if pend:
                cancelar_pendientes(sym, 'orb', 'el precio ya rompió el rango: entra a mercado')
                ya_dentro = posicion(sym, 'orb')[0] != 0 or opero_hoy('orb', hoy)   # una pendiente se llenó justo antes de cancelar
            if not ya_dentro and not plano(sym, 'orb'):
                log('aviso', NOMBRE['orb'], detalle='no pude confirmar que no hay órdenes ni posiciones del rango: no entro a mercado (reintento en el siguiente ciclo)')
                ya_dentro = True
            if not ya_dentro and lotes['orb'] > 0:
                t_o = mt5.symbol_info_tick(sym)
                nivel = hi if lado_m > 0 else lo
                px_o = (t_o.ask if lado_m > 0 else t_o.bid) if t_o is not None else None
                if px_o is None or (px_o - nivel) * lado_m > TOLERANCIA_ORB * nivel:
                    log_cada(('orb_lejos', str(hoy)), 'aviso', NOMBRE['orb'],
                             detalle=f'la ruptura del rango ya pasó y el precio está lejos del nivel ({nivel:,.2f}): no la persigo (la simulación entra en el nivel)')
                else:
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
        if lado_r != 0 and not cerrar(sym, 'ruido', 'salió de la zona · ' + info):
            return                                   # no se confirmó el cierre: no abre el lado contrario (evita quedar cubierto o duplicado)
        if pos_m != 0 and lotes['ruido'] > 0:
            if not plano(sym, 'ruido'):
                return
            t_r = mt5.symbol_info_tick(sym)
            if t_r is None or t_r.bid <= 0 or t_r.ask <= 0:
                log('error', NOMBRE['ruido'], detalle=f'sin tick para abrir zona de ruido ({mt5.last_error()})')
                return
            precio = t_r.ask if pos_m > 0 else t_r.bid
            try:
                c_chk = float(hoy_df.c.loc[ultimo - dt.timedelta(minutes=5)])
            except Exception:
                c_chk = None
            abrir(sym, 'ruido', pos_m, lotes['ruido'], precio * (1 - STOP_EMERGENCIA * pos_m), 'cerró fuera de la zona de ruido · ' + info, ref=c_chk)


def proteger(sym, df):
    """Break even (rango 30 min) y escalera (zona de ruido): sube el stop en el servidor, nunca lo baja."""
    info, t = mt5.symbol_info(sym), mt5.symbol_info_tick(sym)
    if info is None or t is None:
        return
    usd_pt = DOLARES_POR_PUNTO
    for clave in MAGIC:
        _, ps = posicion(sym, clave)
        lpm = lotes_por_mnq(info)
        for p in ps:
            lado = 1 if p.type == mt5.POSITION_TYPE_BUY else -1
            t_in = a_ny(p.time)
            desde = t_in.replace(second=0, microsecond=0)
            desde = desde - dt.timedelta(minutes=desde.minute % 5)
            # Si ruido entró en el último minuto de la vela previa por leve desfase de reloj (ej. 13:59:59), salta a la vela nueva
            if clave != 'orb' and (t_in - desde).total_seconds() >= 240:
                desde += dt.timedelta(minutes=5)
            velas_pos = df[df.index > desde] if clave == 'orb' else df[df.index >= desde]   # ORB entra a media vela: su máximo previo no cuenta
            mejor = max([t.bid] + list(velas_pos.h)) if lado > 0 else min([t.ask] + list(velas_pos.l))
            pts_max = (mejor - p.price_open) * lado
            maxima = pts_max * usd_pt                       # umbrales en escala 1 MNQ (75 pts BE / 100 pts escalera, igual que backtest)
            piso = piso_usd(clave, maxima)
            if piso is None:
                continue
            pts_piso = piso / usd_pt
            mult_mnq = p.volume / max(lpm, 1e-9)
            piso_real, max_real = piso * mult_mnq, maxima * mult_mnq
            nuevo = alinear(info, p.price_open + lado * pts_piso, lado > 0)
            pt = info.point or 0.01
            if p.sl and ((lado > 0 and nuevo <= p.sl + pt) or (lado < 0 and nuevo >= p.sl - pt)):
                continue                                    # el stop ya está igual o mejor
            actual = t.bid if lado > 0 else t.ask
            minimo = (info.trade_stops_level or 0) * pt
            if (lado > 0 and actual - nuevo <= minimo) or (lado < 0 and nuevo - actual <= minimo):
                if cerrar(sym, clave, f'el precio ya está en el piso asegurado (+{piso_real:,.0f} USD / +{pts_piso:.0f} pts)'):
                    _SALIDA_PROT[clave] = ahora_ny()
                continue
            r = mt5.order_send(dict(action=mt5.TRADE_ACTION_SLTP, symbol=sym, position=p.ticket, sl=nuevo, tp=p.tp or 0.0,
                                    magic=MAGIC[clave]))
            if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
                que = 'break even' if clave == 'orb' else f'escalera: asegura +{piso_real:,.0f} USD (+{pts_piso:.0f} pts)'
                log('protege', NOMBRE[clave], 'compra' if lado > 0 else 'venta', p.volume, f'{nuevo:.2f}',
                    f'{que} · llegó a ir +{max_real:,.0f} USD (+{pts_max:.1f} pts) · stop de {p.sl:.2f} a {nuevo:.2f}')
            else:
                log('error', NOMBRE[clave], detalle=f"no pude mover el stop: {r.retcode if r else mt5.last_error()} {r.comment if r else ''}")


TOLERANCIA_ORB = 0.001   # si el bot no tenía orden pendiente al romper (tramo perdido o relanzado), solo entra a menos de 0.1% del nivel
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
# Capas en sombra (decisión de Matheus 24-nov tras AUDIT_014/015): medidas en bps no muestran ventaja (t < 1.5).
# Se calculan y se anotan en la bitácora como «sombra», pero NO cambian el tamaño. Para reactivar una, quítala del conjunto.
CAPAS_SOMBRA = {'cot', 'vix9d', 'nfp', 'cierre_ayer'}
MIEDO_CORTO = 1.10   # VIX9D/VIX al cierre de ayer: arriba de esto, medio tamaño (8 años: esos días −$40/día vs +$35, t −2.4; Sharpe 1.50→1.57)


_SACUDIDA_VISTA = {}


def sacudida(sym, df, hoy):
    """Detector de sacudidas (Trump, noticias, cualquier sorpresa): revisa TODAS las velas de 5 min ya cerradas desde la entrada
    (si el bot estuvo caído o un ciclo tardó, no se salta ninguna). La vela de antes de entrar no cuenta (igual que la simulación)."""
    d = df[df.index.date == hoy]
    if len(d) < 3:
        return
    lado, ps = posicion(sym, 'orb')
    if lado == 0 or not ps:
        return
    t0 = a_ny(ps[0].time).replace(second=0, microsecond=0)
    t0 -= dt.timedelta(minutes=t0.minute % 5)
    tk = ps[0].ticket
    for j in range(1, len(d) - 1):                    # la última vela se está formando
        tj = d.index[j]
        if tj < t0 or (_SACUDIDA_VISTA.get(tk) is not None and tj <= _SACUDIDA_VISTA[tk]):
            continue
        mov = d.c.iloc[j] / d.c.iloc[j - 1] - 1
        if abs(mov) > SACUDIDA and lado * mov < 0:
            if cerrar(sym, 'orb', f'sacudida en contra: la vela de las {tj:%H:%M} NY se movió {mov:+.2%}'):
                _SACUDIDA_VISTA[tk] = tj
            return                                     # si no cerró, la misma vela lo vuelve a intentar en el próximo ciclo
        _SACUDIDA_VISTA[tk] = tj


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
        res = getattr(dl, 'profit', 0.0) + getattr(dl, 'commission', 0.0) + getattr(dl, 'swap', 0.0) + getattr(dl, 'fee', 0.0)
        log('salida', NOMBRE[clave], 'venta' if getattr(dl, 'type', None) == mt5.DEAL_TYPE_SELL else 'compra', getattr(dl, 'volume', ''),
            f"{getattr(dl, 'price', 0.0):.2f}", f'la cerró el servidor por {razones[dl.reason]} · resultado {res:+,.2f} USD · deal {tk}')


def cerrar_viejas(sym, hoy):
    for clave in MAGIC:
        _, ps = posicion(sym, clave)
        if any(a_ny(p.time).date() < hoy for p in ps):
            cerrar(sym, clave, 'quedó abierta de un día anterior')
        if any(a_ny(getattr(o, 'time_setup', 0) or 0).date() < hoy for o in pendientes(sym, clave)):
            cancelar_pendientes(sym, clave, 'orden pendiente de un día anterior')


def resumen(sym, hoy):
    acc = mt5.account_info()
    if acc is None and conectado():
        acc = mt5.account_info()
    if acc is None:
        log('error', detalle='no pude obtener account_info para generar el resumen diario')
        return
    ds = mt5.history_deals_get(dt.datetime.now(UTC) - dt.timedelta(days=2), dt.datetime.now(UTC) + dt.timedelta(days=1)) or []
    L = [f"📊 Update del bot Nasdaq{' FTMO' if CUENTA == 'ftmo' else ' (reglas FTMO)' if MODO == 'ftmo' else ''} — {hoy:%d-%m-%Y}", f'💰 Cuenta: ${acc.equity:,.2f}']
    total, total_ops = 0.0, 0
    for clave in MAGIC:
        mios = [d for d in ds if d.magic == MAGIC[clave] and a_ny(d.time).date() == hoy]
        pnl = sum(d.profit + d.commission + d.swap + getattr(d, 'fee', 0.0) for d in mios)
        n = sum(1 for d in mios if d.entry == mt5.DEAL_ENTRY_IN)
        total += pnl; total_ops += n
        L.append(f"• {NOMBRE[clave]}: {'sin operaciones' if n == 0 else f'{n} operación(es) · {pnl:+,.2f} USD'}")
    L.append(f'🧮 Total del día: {total:+,.2f} USD (base {CONTRATOS:g} MNQ por estrategia, ajustado por volatilidad)')
    opero = total_ops > 0 or any(entrada_anotada(c, hoy) for c in MAGIC)
    L += ftmo_cierre(acc.equity, hoy, opero=opero) if MODO == 'ftmo' else cerrar_dia_examen(acc.equity, hoy)
    L += s50_cierre(acc.equity, hoy, opero)
    errores = 0
    try:
        with open(BITACORA, encoding='utf-8') as fh:
            errores = sum(1 for f in csv.DictReader(fh) if f['evento'] == 'error' and _fecha_ny_log(f['hora_UTC']) == hoy)
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


def balance_medianoche(acc, cierre_prev=None):
    """Balance al empezar el día FTMO (00:00 Praga) = balance actual − lo realizado desde entonces.
    Sin historial (3 intentos): lo MÁS ALTO entre balance, equity y el cierre de ayer (piso más estricto) y avisa."""
    respaldo = max([acc.balance, acc.equity] + ([cierre_prev] if cierre_prev else []))
    try:
        m0 = dt.datetime.now(PRAGA).replace(hour=0, minute=0, second=0, microsecond=0)
        ds = None
        for k in range(3):
            ds = mt5.history_deals_get(m0.astimezone(UTC) - dt.timedelta(days=1), dt.datetime.now(UTC) + dt.timedelta(days=1))
            if ds is not None:
                break
            time.sleep(1)
        if ds is None:
            log('aviso', detalle=f'sin historial de MT5 para el balance de medianoche: uso {respaldo:,.2f} (lo más alto: límite diario más estricto)')
            return respaldo
        tipos = (getattr(mt5, 'DEAL_TYPE_BUY', 0), getattr(mt5, 'DEAL_TYPE_SELL', 1))
        real = sum(d.profit + d.commission + d.swap + getattr(d, 'fee', 0.0) for d in ds
                   if getattr(d, 'type', 0) in tipos and a_ny(d.time).replace(tzinfo=NY).astimezone(PRAGA) >= m0)
        return acc.balance - real
    except Exception:
        log('aviso', detalle=f'no pude calcular el balance de medianoche: uso {respaldo:,.2f} (límite diario más estricto)')
        return respaldo


def ftmo_dia(e, eq, hoy, ref=None):
    """Meta y pisos del día en el reto FTMO. La fase 2 se simula sobre la misma cuenta, con nueva base."""
    f = e['ftmo']; ini = FTMO_INICIAL
    obj = f['base'] + (0.10 if f['fase'] == 1 else 0.05) * ini
    piso = max((eq if ref is None else ref) - 0.05 * ini, f['base'] - 0.10 * ini)   # pérdida diaria (vs saldo al empezar el día; sin posiciones de noche) o máxima (fija)
    if ETAPA == 'fondeada':
        meta = 1e12                                         # cuenta fondeada: sin meta del día
    else:
        meta = 50.0 * ESCALA_FTMO if f['listo'] else max(obj - eq + 50.0 * ESCALA_FTMO, 100.0 * ESCALA_FTMO)   # 100K: $50 / $100
    return dict(fecha=str(hoy), eq_inicio=eq, min_eq=eq, cerrado=False, quemado=False, meta=meta, piso=piso, obj=obj)


def hubo_operaciones(hoy):
    for _ in range(3):
        try:
            ds = mt5.history_deals_get(dt.datetime.now(UTC) - dt.timedelta(days=2), dt.datetime.now(UTC) + dt.timedelta(days=1))
            if ds is not None:
                return any(d.magic in MAGIC.values() and d.entry == mt5.DEAL_ENTRY_IN and a_ny(d.time).date() == hoy for d in ds)
        except Exception:
            pass
        time.sleep(1)
    return any(entrada_anotada(c, hoy) for c in MAGIC)


def ftmo_cierre(equity, hoy, opero=None):
    e = leer_estado(); f = e.get('ftmo'); d = e.get('dia', {})
    if not f:
        return []
    ini = FTMO_INICIAL; L = []
    umbral = AGOTADO_FONDEADA if ETAPA == 'fondeada' else AGOTADO
    agotado = equity <= f['base'] - (0.10 - umbral) * ini
    opero = hubo_operaciones(hoy) if opero is None else bool(opero)   # FTMO solo cuenta como día de trading el que tiene al menos una operación
    if d.get('quemado') and not agotado:
        L.append(f"🛑 Reto FTMO fase {f['fase']}: tocó el freno 0.4% antes del límite (equity {equity:,.0f}); la cuenta sigue viva, mañana sigue.")
    if agotado:
        e.setdefault('historial_ftmo', []).append(dict(fase=f['fase'], etapa=ETAPA, inicio=f['inicio'], fin=str(hoy), resultado='agotado',
                                                       dias=f['dias'] + (1 if opero else 0)))
        if ETAPA == 'reto':
            L.append(f"🔥 Reto FTMO fase {f['fase']} AGOTADO: quedan menos de {umbral:.1%} antes de la pérdida máxima. "
                     f"En real = reto perdido. Mañana arranca un reto nuevo (como comprar otro).")
            ftmo_fase_nueva(e, 1, equity, hoy); guardar_estado(e); return L
        f['aprobada'] = 'agotado'
        quien = 'Cuenta FTMO fondeada' if ETAPA == 'fondeada' else f"Reto FTMO fase {f['fase']}"
        L.append(f"🔥 {quien} AGOTADA (equity {equity:,.0f}; quedan menos de {umbral:.1%} antes de la pérdida máxima): el bot deja de operar esta cuenta. "
                 f"Compra un reto nuevo, cambia los secretos y BOT_FTMO_ETAPA.")
        guardar_estado(e); return L
    f['dias'] += 1 if opero else 0; f['cierre_prev'] = equity
    gan = equity - f['base']; obj = (0.10 if f['fase'] == 1 else 0.05) * ini
    if ETAPA == 'fondeada':
        L.append(f"💼 Cuenta FTMO fondeada · día {f['dias']} · {gan:+,.0f} desde el inicio · pérdida máxima en {f['base'] - 0.10 * ini:,.0f}")
        guardar_estado(e); return L
    f['listo'] = gan >= obj          # se recalcula cada día: si cae debajo de la meta antes de los 4 días, ya no está lista
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


# ===================== Sombra FTMO 50K (0.5×): solo cálculo y registro, nunca toca órdenes ni el estado de 100K =====================
FTMO_50K_INICIAL = 50000.0
FTMO_50K_ESCALA = 0.5            # 3 MNQ en el reto / 2 en la fondeada (en USTEC/US100.cash, la mitad siempre da lotes enteros)
SOMBRA_50K = CUENTA == 'tickmill' and MODO == 'ftmo'
SOMBRA_50K_DESDE = '2026-11-19'  # primer día del ensayo FTMO en Tickmill


def s50_fase_nueva(e, fase, eq, hoy):
    e['ftmo_50k'] = dict(fase=fase, inicio=str(hoy), base=eq, eq=eq, cierre_prev=eq, dias=0, listo=False,
                         ultimo=(e.get('ftmo_50k') or {}).get('ultimo'))


def s50_cerrar_dia(e, fecha, pnl, opero, freno=False):
    """Cierra un día de la sombra con las reglas de FTMO 2-Step 50K (etapa reto: fase 1 y 2 en la misma cuenta). Idempotente por fecha."""
    if 'ftmo_50k' not in e:
        s50_fase_nueva(e, 1, FTMO_50K_INICIAL, fecha)
    s, ini, L = e['ftmo_50k'], FTMO_50K_INICIAL, []
    if s.get('ultimo') and str(fecha) <= s['ultimo']:
        return []
    pnl = round(float(pnl), 2)
    s['eq'] = round(s['eq'] + pnl, 2); s['ultimo'] = str(fecha); s['dias'] += 1 if opero else 0; s['cierre_prev'] = s['eq']
    gan, obj = s['eq'] - s['base'], (0.10 if s['fase'] == 1 else 0.05) * ini
    hist = e.setdefault('historial_ftmo_50k', [])
    quemada = pnl <= -0.05 * ini or s['eq'] <= s['base'] - 0.10 * ini
    agotada = s['eq'] <= s['base'] - (0.10 - AGOTADO) * ini
    if quemada or agotada:
        hist.append(dict(fase=s['fase'], inicio=s['inicio'], fin=str(fecha), resultado='quemada' if quemada else 'agotado', dias=s['dias']))
        L.append(f"🪩 Sombra FTMO 50K (0.5×) fase {s['fase']} {'QUEMADA' if quemada else 'AGOTADA'} (equity {s['eq']:,.0f}): mañana empieza otro reto")
        s50_fase_nueva(e, 1, s['eq'], fecha); return L
    s['listo'] = gan >= obj
    if s['listo'] and s['dias'] >= 4:
        hist.append(dict(fase=s['fase'], inicio=s['inicio'], fin=str(fecha), resultado='aprobada', dias=s['dias']))
        L.append(f"🪩 Sombra FTMO 50K (0.5×): FASE {s['fase']} APROBADA en {s['dias']} días (+${gan:,.0f})")
        s50_fase_nueva(e, 2 if s['fase'] == 1 else 1, s['eq'], fecha); return L
    piso = max(s['eq'] - 0.05 * ini, s['base'] - 0.10 * ini)
    L.append(f"🪩 Sombra FTMO 50K (0.5×) fase {s['fase']} · día {s['dias']} · hoy {pnl:+,.0f} · lleva {gan:+,.0f} de +{obj:,.0f}"
             f"{' (meta lograda)' if s['listo'] else ''}{' · tocó el freno' if freno else ''} · margen mañana ${s['eq'] - piso:,.0f}")
    return L


def backfill_ftmo_50k(e, hoy):
    """Reconstruye (o completa) la sombra con los resúmenes de la bitácora desde SOMBRA_50K_DESDE hasta ayer. Sin duplicar fechas."""
    try:
        with _ARCHIVOS, open(BITACORA, newline='', encoding='utf-8') as fh:
            filas = list(csv.DictReader(fh))
    except Exception:
        return []
    dias = {}
    for r in filas:
        f = (r.get('hora_UTC') or '')[:10]
        if r.get('evento') != 'resumen' or not (SOMBRA_50K_DESDE <= f < str(hoy)) or f in dias:
            continue
        t = r.get('detalle') or ''
        m = re.search(r'Total del día: ([+-]?[\d,]+\.\d+) USD', t)
        if not m:
            continue
        ops = re.findall(r'• [^|:]+: ([^|]+)', t)
        dias[f] = (float(m.group(1).replace(',', '')), any('sin operaciones' not in o for o in ops), 'tocó el freno' in t)
    L = []
    for f in sorted(dias):
        pnl100, opero, freno = dias[f]
        L += s50_cerrar_dia(e, f, round(pnl100 * FTMO_50K_ESCALA, 2), opero, freno)
    return L


def s50_dia(e, hoy=None):
    if 'ftmo_50k' not in e:                                         # AUDIT_012 A2: sin historial, arranca la sombra hoy
        s50_fase_nueva(e, 1, FTMO_50K_INICIAL, hoy or ahora_ny().date())
    s, ini = e['ftmo_50k'], FTMO_50K_INICIAL
    obj = s['base'] + (0.10 if s['fase'] == 1 else 0.05) * ini
    return dict(eq_inicio=s['eq'], min_eq=s['eq'], fijo=None, quemado=False,
                meta=25.0 if s['listo'] else max(obj - s['eq'] + 25.0, 50.0),
                piso=max(s['eq'] - 0.05 * ini, s['base'] - 0.10 * ini), obj=obj)


def s50_intradia(est, R, colchon=None):
    """Congela la sombra si toca su freno o su meta del día. Nunca cambia est['dia']['cerrado'] ni manda órdenes."""
    s50 = (est.get('dia') or {}).get('sombra_50k')
    if not SOMBRA_50K or not s50 or s50.get('fijo') is not None:
        return
    r50 = round(R * FTMO_50K_ESCALA, 2); eq50 = s50['eq_inicio'] + r50
    s50['min_eq'] = min(s50['min_eq'], eq50)
    col = max(FTMO_FRENO * FTMO_50K_INICIAL, colchon or 0.0)        # AUDIT_012 A3: el colchón de 100K escalado (30 pts × $/pt)
    if eq50 <= s50['piso'] + col:
        s50['fijo'], s50['quemado'] = r50, True
        log('sombra50k', detalle=f'sombra 50K: freno (equity virtual {eq50:,.2f} · límite {s50["piso"]:,.2f}) → día fijo en {r50:+,.2f}')
        guardar_estado(est)
    elif r50 >= s50['meta']:
        s50['fijo'] = r50
        log('sombra50k', detalle=f'sombra 50K: meta del día +{s50["meta"]:,.0f} alcanzada → día fijo en {r50:+,.2f}')
        guardar_estado(est)


def s50_cierre(equity, hoy, opero):
    """Cierre del día de la sombra en resumen(): usa lo congelado intradía o la mitad del resultado del día de 100K."""
    if not SOMBRA_50K:
        return []
    try:
        e = leer_estado(); d = e.get('dia') or {}
        if 'ftmo_50k' not in e:
            backfill_ftmo_50k(e, hoy)
        s50 = d.get('sombra_50k') or {}
        pnl = s50['fijo'] if s50.get('fijo') is not None else (equity - d.get('eq_inicio', equity)) * FTMO_50K_ESCALA
        L = s50_cerrar_dia(e, hoy, pnl, opero, bool(s50.get('quemado')))
        guardar_estado(e)
        return L
    except Exception as ex:
        log('aviso', detalle=f'sombra 50K: no pude cerrar el día ({ex})')
        return []


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
    guardia_ip()
    if not iniciar() or mt5.account_info() is None:
        print(f'❌ No pude conectar con MT5 ({mt5.last_error()}): revisa los secretos MT5_LOGIN, MT5_PASSWORD y MT5_SERVER.'); sys.exit(1)
    acc = mt5.account_info()
    print(f"✅ Conectado a la cuenta {cuenta_txt(acc.login)} ({acc.server}) · {'DEMO' if acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else 'REAL (el bot no operaría)'}"
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
    print(f"{'✅' if vh else '⚠️'} Volatilidad (horario normal, 14 días): {vh if vh is None else f'{vh:.2%}'} vs normal {vm if vm is None else f'{vm:.2%}'} → peso {peso:.2f} → {lotes_del_dia(info, peso, peso)[0]:g} MNQ ({lotes_del_dia(info, peso, peso)[2]:g} lotes) con base {CONTRATOS:g}")
    niv = niveles_orb(hoy_df)
    if niv:
        lado, est = modelo_orb(hoy_df, *niv)
        print(f"   {ultimo} · rango 30 min {niv[1]:,.2f}–{niv[0]:,.2f} → {'compra' if lado > 0 else 'venta' if lado < 0 else 'sin operación'} ({est})")
    fin = dt.datetime.combine(ultimo, T('15:55'))
    pos, txt, _ = modelo_ruido(hoy_df, previos, float(previos[-1].c.iloc[-1]) if previos else None, fin)
    print(f"   {ultimo} · zona de ruido al final del día: {'—' if pos is None else {1: 'comprado', -1: 'vendido', 0: 'fuera'}[pos]} · {txt}")
    print('✅ Prueba terminada sin operar.')
    mt5.shutdown()


def pais_ip():
    """País de la IP pública (ipinfo.io y, si falla, api.country.is). None si ninguno responde."""
    for url, leer in (('https://ipinfo.io/country', lambda b: b.decode().strip()),
                      ('https://api.country.is', lambda b: json.loads(b.decode()).get('country', ''))):
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                c = (leer(r.read()) or '').strip().upper()
                if len(c) == 2:
                    return c
        except Exception:
            continue
    return None


def guardia_ip():
    """FTMO prohíbe entrar a MetaTrader desde EE. UU.: se revisa ANTES de conectar. Falla cerrado (sin país verificado, no conecta)."""
    if CUENTA != 'ftmo':
        return
    pais = pais_ip()
    if pais is None or pais == 'US':
        log('error', detalle=('esta IP es de EE. UU.' if pais == 'US' else 'no pude verificar el país de la IP')
                             + ': FTMO prohíbe entrar a MetaTrader desde EE. UU. No me conecto.')
        sys.exit(1)


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
    guardia_ip()
    if not iniciar() or mt5.account_info() is None:
        log('error', detalle=f'no pude conectar con MT5 ({mt5.last_error()})'); sys.exit(1)
    acc = mt5.account_info()
    if acc.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        if CUENTA == 'ftmo' and 'ftmo' in (getattr(acc, 'server', '') or '').lower():
            log('aviso', detalle=f'cuenta FTMO {cuenta_txt(acc.login)} marcada como real en MT5 (capital simulado de FTMO): opero')
        else:
            log('error', detalle=f'la cuenta {cuenta_txt(acc.login)} NO es demo: este bot solo opera en demo'); sys.exit(1)
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
        if 'vix9d' in CAPAS_SOMBRA:
            log('sombra', detalle=f'VIX 9 días / VIX 30 días = {r9:.3f} > {MIEDO_CORTO}: sería ×0.5; en sombra, no cambia el tamaño')
        else:
            f_orb *= 0.5
            log('tamaño', detalle=f'VIX 9 días / VIX 30 días = {r9:.3f} > {MIEDO_CORTO} (miedo de corto plazo) → ×0.5')
    f_ev, nfp, motivos = factor_evento()
    if f_ev != 1.0:
        f_orb *= f_ev
        log('tamaño', detalle=f"{' y '.join(motivos)} → ×{f_ev:g}")
    f_ruido = f_orb
    df_ini = velas(sym)
    prev0 = []
    if df_ini is not None and len(df_ini) > 0:
        _, prev0 = partir_dias(df_ini, hoy)
    try:
        if not prev0:
            raise ValueError('sin días previos disponibles')
        ay = prev0[-1]; pos_ayer = (float(ay.c.iloc[-1]) - float(ay.l.min())) / max(float(ay.h.max() - ay.l.min()), 1e-9)
        f_c = 1.5 if pos_ayer > CIERRE_FUERTE else 0.5 if pos_ayer < CIERRE_DEBIL else 1.0
        if f_c != 1.0 and 'cierre_ayer' in CAPAS_SOMBRA:
            log('sombra', detalle=f"ayer cerró en el {pos_ayer:.0%} de su rango: zona de ruido sería ×{f_c:g}; en sombra, no cambia el tamaño")
        elif f_c != 1.0:
            f_ruido *= f_c
            log('tamaño', detalle=f"ayer cerró en el {pos_ayer:.0%} de su rango → zona de ruido ×{f_c:g}")
    except Exception as e:
        log('aviso', detalle=f'no pude revisar el cierre de ayer ({e})')
    if nfp and 'nfp' in CAPAS_SOMBRA:
        log('sombra', detalle=f'día de empleo (NFP): zona de ruido sería ×{NFP_RUIDO:g}; en sombra, no cambia el tamaño')
    elif nfp:
        f_ruido *= NFP_RUIDO
        log('tamaño', detalle=f'día de empleo (NFP): zona de ruido ×{NFP_RUIDO:g}')
    if MODO == 'ftmo' and (f_orb > TOPE_FTMO or f_ruido > TOPE_FTMO):   # FTMO revisa tamaños «mucho más grandes» que los habituales
        log('tamaño', detalle=f'tope FTMO: máximo {TOPE_FTMO:g}× la base ({CONTRATOS:g} MNQ) por estrategia')
        f_orb, f_ruido = min(f_orb, TOPE_FTMO), min(f_ruido, TOPE_FTMO)
    n_mnq, n_ruido, lotes, lotes_ruido = lotes_del_dia(info, f_orb, f_ruido)
    if info.volume_max and max(lotes, lotes_ruido) > info.volume_max:
        log('aviso', detalle=f'{max(lotes, lotes_ruido)} lotes pasa el máximo por orden del símbolo ({info.volume_max}); uso {info.volume_max}')
        lotes, lotes_ruido = min(lotes, float(info.volume_max)), min(lotes_ruido, float(info.volume_max))
    if v_hoy:
        log('tamaño', detalle=f'volatilidad 14 días {v_hoy:.2%} vs normal {v_med:.2%} → peso {peso:.2f} · '
                              f'hoy: rango 30 min {n_mnq:g} MNQ ({lotes:g} lotes) · zona de ruido {n_ruido:g} MNQ ({lotes_ruido:g} lotes)')
    try:
        est = leer_estado(estricto=True)
    except EstadoDanado as e:
        log('error', detalle=f'el archivo de estado está dañado ({e}): NO opero a ciegas. Revisar {os.path.basename(ESTADO)}'); mt5.shutdown(); sys.exit(1)
    est.pop('examen', None)
    cargar_salidas_prot(hoy)
    if MODO == 'ftmo':
        f0 = est.get('ftmo') or {}
        # AUDIT_014 A1: un estado sin login NO se adopta (podría ser de otra cuenta, p. ej. la prueba gratis del 18-nov al
        # pasar a la cuenta pagada): cae en «cuenta nueva» y se reinicia el seguimiento, sin heredar días ni cierre previo.
        if f0 and f0.get('login') == acc.login:       # estado viejo con el login a la vista: se guarda como identificador
            f0['login'] = id_cuenta(acc.login)
        if not ftmo_estado_es_de(f0, acc.login, ETAPA):
            base_ini = FTMO_INICIAL if (CUENTA == 'ftmo' or ETAPA in ('fase1', 'fase2', 'fondeada')) else acc.balance   # cuenta FTMO: el límite fijo es sobre el capital inicial
            if f0:
                log('aviso', detalle=f"cuenta o etapa nueva (cuenta {cuenta_txt(acc.login)}, etapa {ETAPA}) → reinicio el seguimiento FTMO con base {base_ini:,.2f}")
            est['ftmo'] = dict(login=id_cuenta(acc.login), etapa=ETAPA)
            est.pop('dia', None)
            ftmo_fase_nueva(est, 2 if ETAPA == 'fase2' else 1, base_ini, hoy)
        if est['ftmo'].get('aprobada'):
            que = 'agotada (sin margen antes de la pérdida máxima)' if est['ftmo']['aprobada'] == 'agotado' else 'ya aprobada'
            quien = 'cuenta fondeada' if ETAPA == 'fondeada' else f"fase {est['ftmo']['fase']}"
            log('aviso', detalle=f"{quien} {que} en esta cuenta: no opero. Cambia a la siguiente cuenta y BOT_FTMO_ETAPA.")
            guardar_estado(est); mt5.shutdown(); return
        if est.get('dia', {}).get('fecha') != str(hoy):
            ref = balance_medianoche(acc, (est.get('ftmo') or {}).get('cierre_prev'))
            if abs(ref - acc.equity) > 1:
                log('aviso', detalle=f'balance a medianoche de Praga {ref:,.2f} ≠ equity al arrancar {acc.equity:,.2f}: el límite diario se mide desde el balance de medianoche')
            est['dia'] = ftmo_dia(est, acc.equity, hoy, ref)
            if SOMBRA_50K:
                try:
                    backfill_ftmo_50k(est, hoy)                       # crea la sombra o completa días que falten (idempotente)
                    est['dia']['sombra_50k'] = s50_dia(est, hoy)
                except Exception as ex:
                    log('aviso', detalle=f'sombra 50K: no pude iniciar el día ({ex})')
        if est['ftmo']['listo'] and ETAPA != 'fondeada':                     # relleno hasta los 4 días: 1 MNQ en 100K (2 lotes), 0.5 MNQ en 50K
            n_mnq = 1 if ESCALA_FTMO == 1.0 else ESCALA_FTMO
            lotes = lotes_ruido = lotes_relleno(info)
        guardar_estado(est)
        dd = est['dia']
        meta_txt = f"FTMO {'fondeada · sin meta' if ETAPA == 'fondeada' else 'fase ' + str(est['ftmo']['fase']) + ' · meta del día +' + format(dd['meta'], ',.0f')} · freno en equity {dd['piso'] + FTMO_FRENO * FTMO_INICIAL:,.0f}"
    for v in (VERSIONES if MODO != 'ftmo' else {}):
        if v not in est.get('versiones', {}):
            examen_nuevo(est, v, hoy)
    if MODO != 'ftmo' and (est.get('dia', {}).get('fecha') != str(hoy) or 'v' not in est.get('dia', {})):
        vs = {}
        for v, base in VERSIONES.items():
            n_v = max(1, round(base * f_orb))
            vs[v] = dict(n=n_v, f=(n_v / n_mnq) if n_mnq else 0.0, meta=meta_del_dia(est['versiones'][v]['saldo']), fijo=None, quemado=False)
        est['dia'] = dict(fecha=str(hoy), eq_inicio=acc.equity, min_eq=acc.equity, cerrado=False, v=vs)
    guardar_estado(est)
    if MODO != 'ftmo':
        meta_txt = ' · '.join(f"{v} {s['n']} MNQ meta +{s['meta']:,.0f}" for v, s in est['dia']['v'].items())
    lotes_txt = (f'{lotes:g} lotes por estrategia (≈{n_mnq:g} MNQ)' if lotes == lotes_ruido
                 else f'ORB {lotes:g} lotes (≈{n_mnq:g} MNQ) · ruido {lotes_ruido:g} lotes (≈{n_ruido:g} MNQ)')
    tipo_cta = 'cuenta demo' if acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else f'cuenta {CUENTA.upper()}'
    log('inicio', detalle=f'tramo de la {tramo} · {sym} · {lotes_txt} · equity {acc.equity:,.2f} · '
                          f'{meta_txt} · '
                          f'{tipo_cta} · trabaja hasta las {hasta:%H:%M} NY')
    try:
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
        log('aviso', detalle='SIN CONTEXTO del día (no llegó contexto/hoy.json): sin filtro de Fed por contexto ni gigantes')
    no_opera = str(hoy) in MEDIO_DIA
    if no_opera:
        log('filtro', detalle='medio día de bolsa (cierra 13:00): no opera; la simulación de 8 años no incluye medios días')
    cerrar_viejas(sym, hoy)
    errores = 0
    while True:
        ahora = ahora_ny()
        if ahora.time() >= cierre:
            ok = conectado() and cerrar_todo(sym, f'cierre del día ({cierre:%H:%M} NY)', intentos=5)
            if not ok and ahora_ny().time() < hasta:
                time.sleep(2); continue                    # sigue intentando (y reconectando) hasta el fin del tramo
            if not ok:
                log('error', detalle='NO PUDE CERRAR TODO al final del día: revisar MT5 a mano (quedan posiciones u órdenes)')
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
            acc_now = mt5.account_info()
            if acc_now is None:
                raise RuntimeError(f'account_info devolvió None ({mt5.last_error()})')
            eq = acc_now.equity
            d = est['dia']
            if eq < d['min_eq']:
                d['min_eq'] = eq
            R = eq - d['eq_inicio']
            try:
                s50_intradia(est, R, colchon_freno(sym) * FTMO_50K_ESCALA if MODO == 'ftmo' else None)
            except Exception as ex:
                log_cada('s50', 'aviso', detalle=f'sombra 50K: {ex}', cada=600)
            if MODO == 'ftmo' and not d['cerrado']:
                colchon = colchon_freno(sym)
                if d.get('quemado') or eq <= d['piso'] + colchon:
                    if not d.get('quemado'):
                        d['quemado'] = True
                        log('examen', detalle=f'freno FTMO: equity {eq:,.2f} · límite {d["piso"]:,.2f} · colchón {colchon:,.0f}'); guardar_estado(est)
                    if cerrar_todo(sym, f'FRENO FTMO: equity {eq:,.0f} a menos de {colchon:,.0f} del límite ({d["piso"]:,.0f})', intentos=3):
                        d['cerrado'] = True; guardar_estado(est)
                elif d.get('meta_ok') or R >= d['meta']:
                    if not d.get('meta_ok'):
                        d['meta_ok'] = True
                        log('meta', detalle=f'meta del día FTMO +{d["meta"]:,.0f} alcanzada ({R:+,.0f})'); guardar_estado(est)
                    if cerrar_todo(sym, f'meta del día alcanzada (+{R:,.0f} USD)', intentos=3):
                        d['cerrado'] = True; guardar_estado(est)
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
            if df is not None and not no_opera and not d['cerrado'] and not d.get('quemado') and not d.get('meta_ok'):
                sincronizar(sym, df, hoy, ahora, {'orb': lotes, 'ruido': lotes_ruido}, cierre=cierre)
                sacudida(sym, df, hoy)
                proteger(sym, df)
            if MODO == 'ftmo' and not d['cerrado']:
                asegurar_tope(sym)
            anotar_salidas(sym, hoy, est)
            errores = 0
        except Exception as e:
            errores += 1
            if errores in (1, 10, 50):
                log('error', detalle=f'{type(e).__name__}: {e}'[:200])
        try:
            frenando = MODO == 'ftmo' and (est['dia'].get('quemado') or est['dia'].get('meta_ok')) and not est['dia'].get('cerrado')
            time.sleep(2 if frenando or not plano(sym) else 10)
        except Exception:
            time.sleep(10)
    mt5.shutdown()


if __name__ == '__main__':
    main()
