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
FLUJO_FTMO = 'bot_ftmo.yml'          # cuenta FTMO en el servidor propio de Azure (AUDIT_013 A2)
CIERRE, CIERRE_MEDIO = dt.time(16, 5), dt.time(13, 5)
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


def _hora(c, campo='created_at'):
    return dt.datetime.fromisoformat(c[campo].replace('Z', '+00:00')).astimezone(NY)


def cola_vieja(ahora, corridas, medios):
    """Ids de corridas FTMO en espera que ya no deben correr: de otro día, o de hoy después del cierre (la VM las despertaría mañana
    a las 9:10 ET, antes de que exista el contexto del día)."""
    cierre = CIERRE_MEDIO if str(ahora.date()) in medios else CIERRE
    return [c['id'] for c in corridas if c['status'] in ('queued', 'waiting', 'pending', 'requested')
            and (_hora(c).date() < ahora.date() or ahora.time() >= cierre)]


def vm_apagada(ahora, corridas, feriados, medios):
    """True si en horario de bolsa hay una corrida FTMO esperando servidor hace 15 min o más (la VM no prendió o el runner no conecta)."""
    hoy = str(ahora.date())
    if ahora.weekday() >= 5 or hoy in feriados or not (INICIO <= ahora.time() < (FIN_MEDIO if hoy in medios else FIN)):
        return False
    if any(c['status'] == 'in_progress' for c in corridas):       # AUDIT_014 A6: si algo corre, la VM está prendida
        return False
    return any(c['status'] == 'queued' and (ahora - _hora(c)).total_seconds() >= 900 for c in corridas)


def avisar_issue(texto, marca):
    """Un comentario al día en el issue de FTMO (GitHub manda correo al dueño por la mención)."""
    titulo = '📊 Update diario del bot Nasdaq FTMO'
    issues = json.loads(gh('api', f'repos/{REPO}/issues?state=open&per_page=100'))
    n = next((i['number'] for i in issues if i.get('title') == titulo and 'pull_request' not in i), None)
    if n is None:
        n = json.loads(gh('api', '-X', 'POST', f'repos/{REPO}/issues', '-f', f'title={titulo}', '-f', 'body=Resumen diario del bot FTMO.'))['number']
    desde = dt.datetime.now(NY).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    if any(marca in (c.get('body') or '') for c in json.loads(gh('api', f'repos/{REPO}/issues/{n}/comments?since={desde}&per_page=100'))):
        return
    dueno = os.environ.get('GITHUB_REPOSITORY_OWNER', '')
    gh('api', '-X', 'POST', f'repos/{REPO}/issues/{n}/comments', '-f', f"body={'@' + dueno + chr(10) + chr(10) if dueno else ''}{texto} {marca}")


def vigilar_ftmo(ahora, feriados, medios):
    corridas = json.loads(gh('api', f'repos/{REPO}/actions/workflows/{FLUJO_FTMO}/runs?per_page=30'))['workflow_runs']
    viejas = cola_vieja(ahora, corridas, medios)
    for i in viejas:
        gh('run', 'cancel', str(i), '--repo', REPO)
        print(f'FTMO: cancelé la corrida {i} que seguía en espera fuera de horario')
    corridas = [c for c in corridas if c['id'] not in viejas]     # AUDIT_014 A6: las canceladas ya no cuentan como «en espera»
    if vm_apagada(ahora, corridas, feriados, medios):
        avisar_issue('⚠️ El servidor de FTMO (VM de Azure) no tomó la corrida en 15 min: ¿no prendió o el runner no conecta? '
                     'Revisa la VM en el portal o la app de Azure (o entra por Tailscale).', '<!-- vigia-vm-apagada -->')
        print('::warning::FTMO: corrida en espera hace 15+ min (VM apagada o runner caído); avisé en el issue')
        return
    lanzar, motivo = decidir(ahora, corridas, feriados, medios)
    print(('FTMO RELANZO: ' if lanzar else 'FTMO no hago nada: ') + motivo)
    if lanzar:
        gh('workflow', 'run', FLUJO_FTMO, '--repo', REPO, '--ref', 'main', '-f', 'origen=vigia')
        print(f'::warning::Vigía: relancé el bot FTMO ({motivo})')


def main():
    src = open('bot_nasdaq.py', encoding='utf-8').read()
    corridas = json.loads(gh('api', f'repos/{REPO}/actions/workflows/{FLUJO}/runs?per_page=30'))['workflow_runs']
    lanzar, motivo = decidir(dt.datetime.now(NY), corridas, fechas('FERIADOS', src), fechas('MEDIO_DIA', src))
    print(('RELANZO: ' if lanzar else 'No hago nada: ') + motivo)
    if lanzar:
        gh('workflow', 'run', FLUJO, '--repo', REPO, '--ref', 'main', '-f', 'origen=vigia')
        print(f'::warning::Vigía: relancé el bot ({motivo})')
    try:
        vigilar_ftmo(dt.datetime.now(NY), fechas('FERIADOS', src), fechas('MEDIO_DIA', src))
    except Exception as e:                       # un problema con FTMO nunca frena la vigilancia de Tickmill
        print(f'::warning::Vigía FTMO: {e}')


if __name__ == '__main__':
    sys.exit(main())
