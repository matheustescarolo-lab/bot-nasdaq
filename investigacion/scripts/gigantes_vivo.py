"""Gigantes ×1.5 en vivo: resultado por día (días con reporte de gigantes vs el resto), leído de la bitácora del bot.
Uso: python investigacion/scripts/gigantes_vivo.py [bitacora_nasdaq.csv ...]   (desde la raíz del repo)
Referencia de 8 años (auditoria-reglas.md): la capa aporta +$3.4/día por MNQ base (t 2.6); en 2025–26 solo +$0.6 (t 0.2)."""
import csv, re, sys
from collections import defaultdict

archivos = sys.argv[1:] or ['bitacora_nasdaq.csv']
for arch in archivos:
    vistos, dias = set(), defaultdict(lambda: dict(gig=None, usd=0.0, lotes=0.0, ops=0))
    for r in csv.DictReader(open(arch, encoding='utf-8')):
        clave = tuple(r.values())
        if clave in vistos:                       # la bitácora puede repetir una fila idéntica
            continue
        vistos.add(clave)
        f, ev, det = r['hora_UTC'][:10], r['evento'], r.get('detalle') or ''
        if ev == 'tamaño' and 'gigantes' in det:
            dias[f]['gig'] = re.search(r'gigantes \(([^)]*)\)', det).group(1) if 'gigantes (' in det else 'sí'
        if ev == 'salida':
            m = re.search(r'resultado(?: aprox\.)? ([+-][\d,]+\.\d+) USD', det)
            if m:
                dias[f]['usd'] += float(m.group(1).replace(',', '')); dias[f]['ops'] += 1
                dias[f]['lotes'] = max(dias[f]['lotes'], float(r['lotes'] or 0))
    print(f'== {arch}')
    print('fecha      | gigantes        | ops | resultado US$ | por MNQ (≈ lotes/2)')
    tot = {True: [], False: []}
    for f in sorted(dias):
        d = dias[f]
        if not d['ops']:
            continue
        mnq = d['lotes'] / 2 or 1
        tot[d['gig'] is not None].append(d['usd'] / mnq)
        print(f"{f} | {(d['gig'] or '—')[:15]:15} | {d['ops']:3} | {d['usd']:+12,.2f} | {d['usd'] / mnq:+9,.1f}")
    for g, nom in ((True, 'días de gigantes'), (False, 'resto')):
        v = tot[g]
        print(f"{nom:17}: {len(v)} días · promedio por MNQ {sum(v) / len(v):+,.1f}" if v else f"{nom:17}: sin días con operaciones")
