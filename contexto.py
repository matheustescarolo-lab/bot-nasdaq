"""
CONTEXTO DIARIO — baja de páginas financieras gratuitas lo que importa para el Nasdaq HOY y lo guarda en contexto/AAAA-MM-DD.json
y contexto/hoy.json. No opera. Si una fuente falla, sigue con las demás.
  - Calendario económico de EE. UU. (ForexFactory, impacto alto y medio): Fed, CPI, empleo, PCE, PIB, ventas…
  - Reportes de resultados de los gigantes del Nasdaq-100 (calendario de nasdaq.com): ayer tras el cierre y hoy.
  - Futuros del Nasdaq y del S&P y VIX antes de la apertura (Yahoo Finance).
  - Titulares (CNBC).
  - Flujo: DIX/GEX de SqueezeMetrics y posicionamiento semanal de fondos (COT de la CFTC). Solo se anotan (sombra).
Marcas que usa el bot: decision_fed (no opera el rango de 30 min), y las demás quedan anotadas para el laboratorio.
"""
import os, json, re, datetime as dt, urllib.request, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
NY, MX = ZoneInfo('America/New_York'), ZoneInfo('America/Mexico_City')
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
      'Accept': 'application/json, text/plain, */*'}
GIGANTES = ['NVDA', 'MSFT', 'AAPL', 'AMZN', 'GOOGL', 'GOOG', 'META', 'AVGO', 'TSLA', 'NFLX', 'COST', 'AMD', 'PLTR', 'ASML', 'ADBE']


def bajar(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def calendario(hoy):
    datos = json.loads(bajar('https://nfs.faireconomy.media/ff_calendar_thisweek.json'))
    out = []
    for e in datos:
        if e.get('country') != 'USD' or e.get('impact') not in ('High', 'Medium'):
            continue
        t = dt.datetime.fromisoformat(e['date'])
        if t.astimezone(NY).date() != hoy:
            continue
        out.append(dict(hora_mx=t.astimezone(MX).strftime('%H:%M'), evento=e.get('title'), impacto=e.get('impact'),
                        estimado=e.get('forecast'), anterior=e.get('previous')))
    return sorted(out, key=lambda x: x['hora_mx'])


def reportes(fecha):
    d = json.loads(bajar(f'https://api.nasdaq.com/api/calendar/earnings?date={fecha:%Y-%m-%d}'))
    filas = ((d.get('data') or {}).get('rows')) or []
    out = []
    for f in filas:
        sym = (f.get('symbol') or '').upper()
        if sym in GIGANTES:
            out.append(dict(simbolo=sym, hora=f.get('time'), estimado_eps=f.get('epsForecast'), nombre=f.get('name')))
    return out


def yahoo(sym):
    """Último precio contra el cierre de la sesión anterior (no contra el de hace 5 días)."""
    d = json.loads(bajar(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d'))
    r = d['chart']['result'][0]; m = r['meta']
    cierres = [x for x in (r.get('indicators', {}).get('quote', [{}])[0].get('close') or []) if x is not None]
    precio = m.get('regularMarketPrice')
    dias = [dt.datetime.fromtimestamp(t, NY).date() for t in (r.get('timestamp') or [])][:len(cierres)]
    hoy = dt.datetime.now(NY).date()
    prev = None
    if cierres:                                   # si la última vela es de hoy, el cierre anterior es la penúltima
        prev = cierres[-2] if (dias and dias[-1] >= hoy and len(cierres) > 1) else cierres[-1]
    return dict(precio=precio, cierre_anterior=prev, cambio=(precio / prev - 1) if precio and prev else None)


def titulares(n=8):
    raiz = ET.fromstring(bajar('https://www.cnbc.com/id/100003114/device/rss/rss.html'))
    return [i.findtext('title') for i in raiz.iter('item')][:n]


PALABRAS_MERCADO = re.compile(r'tariff|arancel|china|fed\b|powell|rate|interest|market|stock|trade deal|deal|sanction|nvidia|apple|chip|semiconductor|tax|dollar|oil|war|iran|russia', re.I)


def trump(n=20):
    """Últimos posts de Trump en Truth Social (archivo público trumpstruth.org; si falla, la API de Truth Social)."""
    try:
        raiz = ET.fromstring(bajar('https://trumpstruth.org/feed'))
        posts = [dict(hora=i.findtext('pubDate'), texto=re.sub(r'<[^>]+>', ' ', i.findtext('description') or i.findtext('title') or '').strip()[:400],
                      enlace=i.findtext('link')) for i in raiz.iter('item')][:n]
    except Exception:
        datos = json.loads(bajar('https://truthsocial.com/api/v1/accounts/107780257626128497/statuses?limit=20&exclude_replies=true'))
        posts = [dict(hora=x.get('created_at'), texto=re.sub(r'<[^>]+>', ' ', x.get('content') or '').strip()[:400], enlace=x.get('url')) for x in datos][:n]
    for p in posts:
        p['habla_de_mercado'] = bool(PALABRAS_MERCADO.search(p['texto']))
    return posts


def dealers():
    """DIX (compra en dark pools) y GEX (gamma de los dealers) de SqueezeMetrics: último día y su percentil en 1 año."""
    filas = bajar('https://squeezemetrics.com/monitor/static/DIX.csv', 30).decode().strip().splitlines()[1:]
    f = [r.split(',') for r in filas[-250:]]
    dix = [float(r[2]) for r in f]; gex = [float(r[3]) for r in f]
    pct = lambda xs: round(sum(x <= xs[-1] for x in xs) / len(xs), 2)
    return dict(fecha=f[-1][0], dix=round(dix[-1], 4), dix_pct=pct(dix), gex=round(gex[-1] / 1e9, 2), gex_pct=pct(gex))


def fondos(hoy):
    """COT de la CFTC (Nasdaq-100 consolidado): posición neta de los fondos apalancados / interés abierto y su cambio en la semana.
    Laboratorio 8 años: si recortan fuerte (cambio < -2.6 pp) nuestras estrategias ganan mucho menos esa semana (t≈2.5). En sombra."""
    import io, csv, zipfile
    filas = []
    for y in (hoy.year - 1, hoy.year):
        try:
            z = zipfile.ZipFile(io.BytesIO(bajar(f'https://www.cftc.gov/files/dea/history/fut_fin_txt_{y}.zip', 60)))
            filas += [r for r in csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding='latin-1'))
                      if 'NASDAQ-100 Consolidated' in r['Market_and_Exchange_Names']]
        except Exception:
            pass
    filas.sort(key=lambda r: r['Report_Date_as_YYYY-MM-DD'])
    neto = lambda r: (float(r['Lev_Money_Positions_Long_All']) - float(r['Lev_Money_Positions_Short_All'])) / float(r['Open_Interest_All'])
    a, b = filas[-2], filas[-1]; cambio = neto(b) - neto(a)
    return dict(reporte=b['Report_Date_as_YYYY-MM-DD'], neto_apalancados=round(neto(b), 4), cambio_semana=round(cambio, 4),
                lectura='recortaron fuerte' if cambio < -0.0259 else 'aumentaron fuerte' if cambio > 0.0233 else 'normal')


def anterior_habil(d):
    d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def main():
    ahora = dt.datetime.now(NY); hoy = ahora.date(); ayer = anterior_habil(hoy)
    c = dict(fecha=str(hoy), generado_ny=ahora.strftime('%Y-%m-%d %H:%M'), errores={})
    for clave, fn in [('calendario', lambda: calendario(hoy)), ('reportes_ayer', lambda: reportes(ayer)),
                      ('reportes_hoy', lambda: reportes(hoy)), ('titulares', titulares), ('trump', trump),
                      ('nasdaq_futuro', lambda: yahoo('NQ=F')), ('sp_futuro', lambda: yahoo('ES=F')), ('vix', lambda: yahoo('%5EVIX')), ('vix9d', lambda: yahoo('%5EVIX9D')), ('dealers', dealers), ('fondos', lambda: fondos(hoy))]:
        try:
            c[clave] = fn()
        except Exception as e:
            c[clave] = None; c['errores'][clave] = f'{type(e).__name__}: {e}'[:200]
    eventos = ' | '.join(e['evento'] or '' for e in (c.get('calendario') or []))
    c['marcas'] = dict(
        decision_fed=bool(re.search(r'Federal Funds Rate|FOMC Statement', eventos, re.I)),
        minutas_fed=bool(re.search(r'FOMC Meeting Minutes', eventos, re.I)),
        cpi=bool(re.search(r'\bCPI\b', eventos)),
        empleo_nfp=bool(re.search(r'Non-Farm|Nonfarm', eventos, re.I)),
        pce=bool(re.search(r'\bPCE\b', eventos)),
        gigantes_reportaron_ayer_tras_cierre=[r['simbolo'] for r in (c.get('reportes_ayer') or []) if 'after' in (r.get('hora') or '').lower()],
        gigantes_reportan_hoy_antes=[r['simbolo'] for r in (c.get('reportes_hoy') or []) if 'pre' in (r.get('hora') or '').lower()],
        gigantes_reportan_hoy_tras_cierre=[r['simbolo'] for r in (c.get('reportes_hoy') or []) if 'after' in (r.get('hora') or '').lower()],
        gap_nasdaq_futuro=(c.get('nasdaq_futuro') or {}).get('cambio'),
        vix=(c.get('vix') or {}).get('precio'),
        vix9d_vix=round(c['vix9d']['cierre_anterior'] / c['vix']['cierre_anterior'], 3) if (c.get('vix9d') or {}).get('cierre_anterior') and (c.get('vix') or {}).get('cierre_anterior') else None,
        dix_pct=(c.get('dealers') or {}).get('dix_pct'), gex_pct=(c.get('dealers') or {}).get('gex_pct'),
        fondos_semana=(c.get('fondos') or {}).get('lectura'),
        trump_posts_de_mercado=sum(1 for p in (c.get('trump') or []) if p.get('habla_de_mercado')))
    os.makedirs(os.path.join(HERE, 'contexto'), exist_ok=True)
    for nombre in (f'{hoy}.json', 'hoy.json'):
        with open(os.path.join(HERE, 'contexto', nombre), 'w', encoding='utf-8') as fh:
            json.dump(c, fh, ensure_ascii=False, indent=1)
    m = c['marcas']
    print(f"Contexto {hoy}: {len(c.get('calendario') or [])} eventos ({eventos or 'ninguno'}) · decisión Fed {m['decision_fed']} · minutas {m['minutas_fed']} · "
          f"reportaron ayer {m['gigantes_reportaron_ayer_tras_cierre']} · hoy antes {m['gigantes_reportan_hoy_antes']} · hoy después {m['gigantes_reportan_hoy_tras_cierre']} · "
          f"futuro Nasdaq {m['gap_nasdaq_futuro']} · VIX {m['vix']} · VIX9D/VIX {m['vix9d_vix']} · Trump: {len(c.get('trump') or [])} posts ({m['trump_posts_de_mercado']} de mercado) · DIX pct {m['dix_pct']} · GEX pct {m['gex_pct']} · fondos {m['fondos_semana']} · errores {c['errores']}")


if __name__ == '__main__':
    main()
