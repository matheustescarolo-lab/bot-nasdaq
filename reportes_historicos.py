"""Baja del calendario de nasdaq.com las fechas de reporte de los gigantes del Nasdaq-100 desde 2019 (día por día). No opera."""
import json, time, datetime as dt, urllib.request, csv
from contexto import GIGANTES, UA
filas, d, fin = [], dt.date(2019, 1, 1), dt.date.today()
while d <= fin:
    if d.weekday() < 5:
        for intento in range(3):
            try:
                req = urllib.request.Request(f'https://api.nasdaq.com/api/calendar/earnings?date={d:%Y-%m-%d}', headers=UA)
                datos = json.loads(urllib.request.urlopen(req, timeout=20).read())
                for f in ((datos.get('data') or {}).get('rows')) or []:
                    if (f.get('symbol') or '').upper() in GIGANTES:
                        filas.append(dict(fecha=str(d), simbolo=f['symbol'].upper(), hora=f.get('time'), eps_estimado=f.get('epsForecast'),
                                          eps_real=f.get('eps'), sorpresa=f.get('surprise')))
                break
            except Exception as e:
                time.sleep(2)
        time.sleep(0.25)
    d += dt.timedelta(days=1)
with open('reportes_gigantes.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=['fecha', 'simbolo', 'hora', 'eps_estimado', 'eps_real', 'sorpresa']); w.writeheader(); w.writerows(filas)
print(len(filas), 'reportes')
