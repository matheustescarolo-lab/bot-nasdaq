"""Baja del calendario de nasdaq.com las fechas de reporte de los gigantes del Nasdaq-100 desde 2019 (día por día). No opera."""
import json, time, datetime as dt, urllib.request, csv, sys, os
from concurrent.futures import ThreadPoolExecutor
from contexto import GIGANTES, UA
año = int(sys.argv[1]) if len(sys.argv) > 1 else None
ini, fin = (dt.date(año, 1, 1), min(dt.date(año, 12, 31), dt.date.today())) if año else (dt.date(2019, 1, 1), dt.date.today())
dias = [ini + dt.timedelta(days=i) for i in range((fin - ini).days + 1) if (ini + dt.timedelta(days=i)).weekday() < 5]
def uno(d):
    out = []
    for intento in range(3):
        try:
            req = urllib.request.Request(f'https://api.nasdaq.com/api/calendar/earnings?date={d:%Y-%m-%d}', headers=UA)
            datos = json.loads(urllib.request.urlopen(req, timeout=15).read())
            for f in ((datos.get('data') or {}).get('rows')) or []:
                if (f.get('symbol') or '').upper() in GIGANTES:
                    out.append(dict(fecha=str(d), simbolo=f['symbol'].upper(), hora=f.get('time'), eps_estimado=f.get('epsForecast'),
                                    eps_real=f.get('eps'), sorpresa=f.get('surprise')))
            return out
        except Exception:
            time.sleep(2)
    return out
with ThreadPoolExecutor(6) as ex:
    filas = [r for lst in ex.map(uno, dias) for r in lst]
with open(f'reportes_gigantes{"_" + str(año) if año else ""}.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=['fecha', 'simbolo', 'hora', 'eps_estimado', 'eps_real', 'sorpresa']); w.writeheader(); w.writerows(filas)
print(len(filas), 'reportes')
