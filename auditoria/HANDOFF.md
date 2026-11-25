# HANDOFF para Neon — AUDIT_016: 4 capas pasan a sombra (decisión de Matheus tras AUDIT_014/015)

Audita `git diff c2f8c12..HEAD -- '*.py'`. Cambio pequeño y de estrategia, ya aprobado por Matheus («sí», 24-nov):
las capas **COT ×0.5, VIX9D/VIX ×0.5, NFP ruido ×1.5 y cierre de ayer ×1.5/×0.5** dejan de cambiar el tamaño.
Motivo: tu AUDIT_014/015 y la respuesta de Claude (bps, t < 1.5 cada una; PBO entre capas 31%).

## Qué cambió
- `bot_nasdaq.py`:
  - Nuevo conjunto `CAPAS_SOMBRA = {'cot', 'vix9d', 'nfp', 'cierre_ayer'}`.
  - `factor_evento()`: el COT se anota como evento `sombra` en la bitácora y no multiplica; **gigantes ×1.5 sigue activo**.
  - Bloque de tamaño de `main`: VIX9D, cierre de ayer y NFP se anotan como `sombra` («sería ×…; en sombra, no cambia el tamaño») y no multiplican.
  - Siguen activos: tamaño por volatilidad, gigantes, filtro de caída, sin ORB en Fed, tope 2×, y todas las protecciones FTMO.
- `tests/test_bot.py`: `test_capas_en_sombra_no_cambian_el_tamano` (COT y NFP no cambian el factor; gigantes sí; las 4 ramas consultan `CAPAS_SOMBRA`). 74 pruebas OK.
- `investigacion/scripts/capas_sombra.py`: efecto en la simulación (8 años, $/día por MNQ base, Sharpe):

| Versión | Todo | 2019–22 | 2023–26 | 2025–26 |
|---|---|---|---|---|
| Anterior (8 capas) | $38.9 (1.79) | $26.0 (1.71) | $51.9 (1.94) | $49.8 |
| Nuevo (4 en sombra) | $36.2 (1.66) | $26.0 (1.67) | $46.4 (1.75) | $37.8 |

La caída in-sample (−$2.7/día) es la esperada: esas capas se eligieron con los mismos datos. La expectativa para planificar sigue siendo el núcleo con costos altos (~$20–30/día por MNQ base).

## Qué revisar
1. Que ninguna de las 4 capas siga cambiando `f_orb`/`f_ruido` por otro camino (incluida la sombra FTMO 50K y `--prueba`).
2. Que gigantes, volatilidad, filtro de caída, Fed y tope 2× sigan iguales.
3. Que la bitácora deje rastro suficiente para medir cada capa en vivo (evento `sombra`).
4. El aviso «SIN CONTEXTO» ahora dice «sin filtro de Fed por contexto ni gigantes» (el VIX9D ya no recorta).

## Ya tomado (no reabrir)
La decisión de pasar estas 4 capas a sombra (Matheus). Todo lo aprobado en AUDIT_005–015.

---

# Cierre: AUDIT_016 — APROBADO (ronda 1)
Claude lo verificó por su lado antes del veredicto: 74/74 pruebas OK en una copia. `COT_RECORTE`, `NFP_RUIDO`, `MIEDO_CORTO` y `CIERRE_FUERTE/DEBIL` solo se usan en las 4 ramas protegidas por `CAPAS_SOMBRA`; no hay otro camino que cambie `f_orb`/`f_ruido`.
Notas BAJO de Neon, sin cambio ahora (no bloquean, y tocar el cálculo de tamaño sin necesidad agrega riesgo antes del 1-dic):
- A1: cuando se vuelva a tocar el tamaño, extraer el bloque a una función pura (`factores_tamano`) y probar en ejecución las 4 ramas en sombra y activadas.
- A2: al medir las capas en vivo, contar los eventos `sombra` una vez por fecha de NY (se repiten en cada tramo). El aviso «SIN CONTEXTO» se actualiza solo si se reactiva alguna capa que dependa del contexto.