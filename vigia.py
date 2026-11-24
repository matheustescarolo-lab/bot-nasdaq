"""Vigía del bot Nasdaq: si en horario de bolsa no hay ninguna corrida del bot activa ni en espera, la vuelve a lanzar.
Nunca cancela ni duplica un tramo (solo lanza si no hay nada activo). Como máximo 4 relanzamientos por día."""
import datetime as dt
import json
import os
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

NY = ZoneInfo('America/New_York')
REPO = os.environ.get('GITHUB_REPOSITORY', 'matheustescarolo-lab/bot-nasdaq')
FLUJO = 'bot_nasdaq.yml'
MAX_RELANZAMIENTOS = 4
INICIO, FIN, FIN_MEDIO = dt.time(9, 50), dt.time(15, 45), dt.time(12, 45)


def fechas(nombre, src):
    m = re.search(nombre + r"\s*=\s*\{([^}]*)\}", src, re.S)
    return set(re.findall(r"'(\d{4}-\d\d-\d\d)'", m.group(1))) if m else set()


def gh(*args):
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True).stdout


def decidir(ahora, corridas, feriados, medios):
    """Devuelve (lanzar, motivo). corridas: dicts de la API (status, conclusion, created_at, updated_at, display_title)."""
    hoy = str(ahora.date())
    fin = FIN_MEDIO if hoy in medios else FIN
    if ahora.weekday() >= 5 or hoy in feriados or not (INICIO <= ahora.time() < fin):
        return False, 'fuera del horario de bolsa'
    if any(c['status'] != 'completed' for c in corridas):
        return False, 'ya hay una corrida activa o en espera'
    de_hoy = [c for c in corridas if dt.datetime.fromisoformat(c['created_at'].replace('Z', '+00:00')).astimezone(NY).date() == ahora.date()
              and 'prueba' not in (c.get('display_title') or '').lower()]          # una prueba no dice nada del bot de hoy (AUDIT_010 A4)
    if sum('vigia' in (c.get('display_title') or '').lower() for c in de_hoy) >= MAX_RELANZAMIENTOS:
        return False, f'ya relancé {MAX_RELANZAMIENTOS} veces hoy: no insisto (revisar a mano)'
    if de_hoy:
        u = max(de_hoy, key=lambda c: c['created_at'])
        if u.get('conclusion') == 'cancelled':
            return False, 'la última corrida fue cancelada (paro manual): no relanzo'
        dur = (dt.datetime.fromisoformat(u['updated_at'].replace('Z', '+00:00'))
               - dt.datetime.fromisoformat(u['created_at'].replace('Z', '+00:00'))).total_seconds()
        if u.get('conclusion') == 'success' and dur < 240 and 'vigia' not in (u.get('display_title') or '').lower():
            return False, 'la última corrida terminó bien en minutos (el bot decidió no operar): no relanzo'
        if u.get('conclusion') == 'success' and dur < 240 and 'vigia' in (u.get('display_title') or '').lower():
            return False, 'mi último relanzamiento terminó bien en minutos (el bot decidió no operar): no insisto'
    return True, 'no hay ninguna corrida del bot en horario de bolsa'


def main():
    src = open('bot_nasdaq.py', encoding='utf-8').read()
    corridas = json.loads(gh('api', f'repos/{REPO}/actions/workflows/{FLUJO}/runs?per_page=30'))['workflow_runs']
    lanzar, motivo = decidir(dt.datetime.now(NY), corridas, fechas('FERIADOS', src), fechas('MEDIO_DIA', src))
    print(('RELANZO: ' if lanzar else 'No hago nada: ') + motivo)
    if lanzar:
        gh('workflow', 'run', FLUJO, '--repo', REPO, '--ref', 'main', '-f', 'origen=vigia')
        print(f'::warning::Vigía: relancé el bot ({motivo})')


if __name__ == '__main__':
    sys.exit(main())
