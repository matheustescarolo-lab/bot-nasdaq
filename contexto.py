"""
CONTEXTO DIARIO — baja de páginas financieras gratuitas lo que importa para el Nasdaq HOY y lo guarda en contexto/AAAA-MM-DD.json
y contexto/hoy.json. No opera. Si una fuente falla, sigue con las demás.
  - Calendario económico de EE. UU. (ForexFactory, impacto alto y medio): Fed, CPI, empleo, PCE, PIB, ventas…
  - Reportes de resultados de los gigantes del Nasdaq-100 (calendario de nasdaq.com): ayer tras el cierre y hoy.
  - Futuros del Nasdaq y del S&P y VIX antes de la apertura (Yahoo Finance).
  - Titulares (CNBC).
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
    d = json.loads(bajar(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d'))
    m = d['chart']['result'][0]['meta']
    precio, prev = m.get('regularMarketPrice'), m.get('chartPreviousClose') or m.get('previousClose')
    return dict(precio=precio, cierre_anterior=prev, cambio=(precio / prev - 1) if precio and prev else None)


def titulares(n=8):
    raiz = ET.fromstring(bajar('https://www.cnbc.com/id/100003114/device/rss/rss.html'))
    return [i.findtext('title') for i in raiz.iter('item')][:n]


def anterior_habil(d):
    d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def main():
    ahora = dt.datetime.now(NY); hoy = ahora.date(); ayer = anterior_habil(hoy)
    c = dict(fecha=str(hoy), generado_ny=ahora.strftime('%Y-%m-%d %H:%M'), errores={})
    for clave, fn in [('calendario', lambda: calendario(hoy)), ('reportes_ayer', lambda: reportes(ayer)),
                      ('reportes_hoy', lambda: reportes(hoy)), ('titulares', titulares),
                      ('nasdaq_futuro', lambda: yahoo('NQ=F')), ('sp_futuro', lambda: yahoo('ES=F')), ('vix', lambda: yahoo('%5EVIX'))]:
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
        vix=(c.get('vix') or {}).get('precio'))
    os.makedirs(os.path.join(HERE, 'contexto'), exist_ok=True)
    for nombre in (f'{hoy}.json', 'hoy.json'):
        with open(os.path.join(HERE, 'contexto', nombre), 'w', encoding='utf-8') as fh:
            json.dump(c, fh, ensure_ascii=False, indent=1)
    m = c['marcas']
    print(f"Contexto {hoy}: {len(c.get('calendario') or [])} eventos ({eventos or 'ninguno'}) · decisión Fed {m['decision_fed']} · minutas {m['minutas_fed']} · "
          f"reportaron ayer {m['gigantes_reportaron_ayer_tras_cierre']} · hoy antes {m['gigantes_reportan_hoy_antes']} · hoy después {m['gigantes_reportan_hoy_tras_cierre']} · "
          f"futuro Nasdaq {m['gap_nasdaq_futuro']} · VIX {m['vix']} · errores {list(c['errores'])}")


if __name__ == '__main__':
    main()
