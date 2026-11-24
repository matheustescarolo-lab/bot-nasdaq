"""Auditoría automática con Gemini («Neon») en GitHub Actions.
Manda a Gemini: reglas (AUDITOR.md), HANDOFF.md, el diff de la rama contra main y los archivos completos que cambiaron.
Guarda auditoria/AUDIT_NNN.md y deja el veredicto en GITHUB_OUTPUT. Solo usa la biblioteca estándar."""
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = 'https://generativelanguage.googleapis.com/v1beta'
CARPETA = 'auditoria'
SIEMPRE = ['bot_nasdaq.py', 'estrategias.py']
CODIGO = re.compile(r'(\.py|\.ya?ml|\.md)$')
MAX_ARCHIVO = 400_000


def git(*a):
    return subprocess.run(['git', *a], check=True, capture_output=True, text=True).stdout


class SinCuota(Exception):
    pass


def pedir(url, cuerpo=None, intentos=4):
    for k in range(intentos):
        try:
            req = urllib.request.Request(url, data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detalle = e.read().decode(errors='replace')[:500]
            if e.code == 429 and 'quota' in detalle.lower() and 'exceeded your current quota' in detalle.lower():
                raise SinCuota(detalle)                    # el plan no incluye este modelo (o se acabó la cuota del día): no sirve reintentar
            if e.code in (429, 500, 503) and k < intentos - 1:
                print(f'Gemini respondió {e.code}; reintento en {30 * (k + 1)} s', flush=True)
                time.sleep(30 * (k + 1)); continue
            raise SystemExit(f'Error de la API de Gemini {e.code}: {detalle}')


def generar(llave, modelo, prompt):
    """Pide la auditoría en modo streaming (SSE): la conexión no se queda muda 10+ min esperando la respuesta completa."""
    cuerpo = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0.2}}
    for k in range(3):
        req = urllib.request.Request(f'{API}/{modelo}:streamGenerateContent?alt=sse&key={llave}',
                                     data=json.dumps(cuerpo).encode(), headers={'Content-Type': 'application/json'})
        texto, t0, aviso = [], time.time(), 0
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                for linea in r:
                    linea = linea.decode('utf-8', errors='replace').strip()
                    if not linea.startswith('data:'):
                        continue
                    d = json.loads(linea[5:])
                    for parte in (d.get('candidates') or [{}])[0].get('content', {}).get('parts', []):
                        if not parte.get('thought'):
                            texto.append(parte.get('text', ''))
                    n = sum(map(len, texto))
                    if n - aviso >= 4000:
                        aviso = n; print(f'  … {n:,} caracteres recibidos ({time.time() - t0:.0f} s)', flush=True)
            return ''.join(texto).strip()
        except urllib.error.HTTPError as e:
            detalle = e.read().decode(errors='replace')[:500]
            if e.code == 429 and 'exceeded your current quota' in detalle.lower():
                raise SinCuota(detalle)
            if e.code in (429, 500, 503) and k < 2:
                print(f'Gemini respondió {e.code}; reintento en {60 * (k + 1)} s', flush=True)
                time.sleep(60 * (k + 1)); continue
            raise SystemExit(f'Error de la API de Gemini {e.code}: {detalle}')
        except (TimeoutError, OSError) as e:
            print(f'::warning::{modelo} no respondió ({e}); {"reintento" if k < 2 else "paso al siguiente"}', flush=True)
    raise SinCuota('sin respuesta')


def version(nombre):
    return tuple(int(x) for x in re.findall(r'\d+', nombre.split('/')[-1])[:3]) or (0,)


def modelos(llave):
    """Candidatos en orden: GEMINI_MODEL si está; si no, el «pro» más nuevo y, como respaldo (plan gratuito), el «flash» más nuevo."""
    pedido = os.environ.get('GEMINI_MODEL', '').strip()
    if pedido:
        return [pedido if pedido.startswith('models/') else 'models/' + pedido]
    ms = pedir(f'{API}/models?pageSize=1000&key={llave}').get('models', [])
    nombres = [m['name'] for m in ms if 'generateContent' in m.get('supportedGenerationMethods', [])
               and not re.search(r'tts|image|vision|embedding|audio|live|lite|nano|gemma', m['name'])]
    orden = lambda n: (version(n), 'preview' not in n, 'exp' not in n)
    pro = sorted([n for n in nombres if 'pro' in n], key=orden, reverse=True)[:2]
    flash = sorted([n for n in nombres if 'flash' in n], key=orden, reverse=True)[:2]
    if not pro + flash:
        raise SystemExit('No encontré un modelo Gemini con generateContent; define la variable GEMINI_MODEL.')
    return pro + flash


def leer(ruta):
    try:
        with open(ruta, encoding='utf-8') as fh:
            t = fh.read()
        return t if len(t) <= MAX_ARCHIVO else t[:MAX_ARCHIVO] + '\n[… recortado …]'
    except FileNotFoundError:
        return None


def main():
    llave = os.environ.get('GEMINI_API_KEY', '').strip()
    seco = '--seco' in sys.argv
    if not llave and not seco:
        raise SystemExit('Falta el secreto GEMINI_API_KEY en el repositorio.')
    rama = os.environ.get('RAMA') or git('rev-parse', '--abbrev-ref', 'HEAD').strip()
    commit = git('rev-parse', '--short', 'HEAD').strip()
    base = os.environ.get('BASE', '').strip() or git('merge-base', 'origin/main', 'HEAD').strip()   # BASE: auditar desde un commit (p. ej. algo ya subido a main)
    diff = git('diff', f'{base}..HEAD', '--', '*.py', '.github/workflows/*', 'investigacion/*.md', 'auditoria/HANDOFF.md')
    cambiados = [f for f in git('diff', '--name-only', f'{base}..HEAD').split() if CODIGO.search(f) and not f.startswith(f'{CARPETA}/AUDIT_')]
    archivos = list(dict.fromkeys(SIEMPRE + [f for f in cambiados if f.endswith('.py') or f.endswith('.yml')]))
    previas = sorted(glob.glob(f'{CARPETA}/AUDIT_*.md'))
    n = max([int(re.findall(r'(\d+)', os.path.basename(p))[0]) for p in previas] + [0]) + 1
    salida = f'{CARPETA}/AUDIT_{n:03d}.md'
    partes = [leer(f'{CARPETA}/AUDITOR.md'),
              f'\n# Tarea\nAudita la rama `{rama}` (commit {commit}) contra {base[:7]}. Escribe la auditoría número {n:03d} con el formato exacto de arriba. '
              'Responde SOLO con el contenido de la auditoría en Markdown, en español, citando archivo:línea del código que se te da.',
              '\n# auditoria/HANDOFF.md (lo que Claude dice que hizo)\n' + (leer(f'{CARPETA}/HANDOFF.md') or '(no hay HANDOFF.md)')]
    if previas:
        partes.append(f'\n# Auditoría anterior ({os.path.basename(previas[-1])})\n' + leer(previas[-1]))
    partes.append(f'\n# Diff main..{rama}\n```diff\n{diff}\n```')
    for f in archivos:
        t = leer(f)
        if t is not None:
            numerado = '\n'.join(f'{i + 1:5d}  {l}' for i, l in enumerate(t.split('\n')))
            partes.append(f'\n# Archivo completo: {f} (con números de línea)\n```\n{numerado}\n```')
    prompt = '\n'.join(partes)
    print(f'Rama {rama} · commit {commit} · {len(archivos)} archivos · {len(prompt):,} caracteres → {salida}', flush=True)
    if seco:
        print(prompt[:3000]); return 0
    texto = modelo = None
    for modelo in modelos(llave):
        print(f'Modelo: {modelo}', flush=True)
        try:
            texto = generar(llave, modelo, prompt)
            if texto:
                break
            print(f'::warning::{modelo} devolvió una respuesta vacía', flush=True)
        except SinCuota:
            print(f'::warning::Sin cuota (o sin respuesta) de {modelo}: pruebo el siguiente', flush=True)
    if not texto:
        raise SystemExit('Ningún modelo de Gemini respondió con este plan (activar facturación o definir GEMINI_MODEL).')
    texto = re.sub(r'^```(?:markdown)?\s*|\s*```$', '', texto)
    m = re.search(r'\*\*Veredicto:\*\*\s*(APROBADO CON CAMBIOS|APROBADO|RECHAZADO)', texto)
    veredicto = m.group(1) if m else 'SIN VEREDICTO'
    with open(salida, 'w', encoding='utf-8') as fh:
        fh.write(f'<!-- rama {rama} · commit {commit} · modelo {modelo.split("/")[-1]} · {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())} -->\n{texto}\n')
    print(f'Veredicto: {veredicto}')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            fh.write(f'veredicto={veredicto}\narchivo={salida}\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as fh:
            fh.write(texto + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
