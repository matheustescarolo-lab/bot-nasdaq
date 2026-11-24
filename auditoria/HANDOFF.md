# HANDOFF para Neon — AUDIT_012: correcciones de AUDIT_011

Audita `git diff 06d938d..5139f00 -- '*.py' .github/` (rama audit-011, ya en main). Son las correcciones de tu AUDIT_011 (APROBADO CON CAMBIOS). Claude verificó los 3 hallazgos: los 3 son reales. 64 pruebas; todas pasan también corridas una por una, y las nuevas fallan con el código anterior. Reglas de las estrategias: sin cambios.

## Qué se hizo
| # | Veredicto de Claude | Cambio |
|---|---|---|
| A1 MEDIO | Real | `lotes_pendientes_otras(sym, excluir)`. La reserva frente a la pendiente de la otra estrategia usa el margen con el colchón de cuando se llene. En `asegurar_tope`: `margen_ftmo(sym, lp, solo_realizado=True)`. En `tope_stop`: `margen_ftmo(sym, lotes + lp, solo_realizado=True)`. Con 24 + 24 lotes, ruido $3,060 + pendiente $500 = $3,560 = margen proyectado (antes $4,280). También `riesgo_abierto(sym, excluir=clave)` en `tope_stop` (tu nota). Prueba: `test_a1_pendiente_con_el_colchon_de_cuando_se_llene`. |
| A2 BAJO | Real (las 4 fallaban solas) | `setUp` deja `positions_get`, `orders_get` y `history_deals_get` en `[]`. Se corrieron las 64 pruebas una por una: todas pasan. |
| A3 BAJO | Real | `opero` se evalúa antes del agotado. `historial_ftmo` guarda `etapa` y `dias + (1 if opero else 0)`. Los textos dicen «Cuenta FTMO fondeada» o «cuenta fondeada» en esa etapa e incluyen el umbral. |

## Tu pregunta 1 (agotado en la fondeada)
- Tenías razón en la lógica: en la fondeada no hay meta y toda ganancia se cobra.
- Ahora: `AGOTADO = 0.02` (reto/fase1/fase2) y `AGOTADO_FONDEADA = 0.008`.
- Se midió con `investigacion/scripts/freno_v4.py`, que además corrige tus dos notas sobre el simulador:
  - Solo cuentan días con operaciones.
  - Si el deslizamiento del freno llega al límite, es quema.
- Y modela lo que hace el bot al lograr la meta antes de los 4 días: sigue con 1 MNQ y meta de $50.

| Agotado | No cobra (pruebas / mitad) | Mediana 12 m |
|---|---|---|
| 0.8% en todo (antes) | 14% / 26% | $24.6k / $12.3k |
| 2% en todo | 14% / 25% | $24.9k / $14.3k |
| **2% en reto y fases, 0.8% en la fondeada (ahora)** | **14% / 25%** | **$25.0k / $14.3k** |

Mejora en las dos mitades de años.

## Tu pregunta 2 (vigía + workflow_run)
- No se verificó en GitHub si una corrida lanzada por el vigía con `github.token` dispara otra vez `workflow_run` al terminar.
- En el peor caso, una segunda caída queda cubierta por el `schedule` cada 15 min: hasta 15 min sin bot.
- Se acepta; se revisará al montar el runner propio en México (enero).
- `c1e.py` (M0 fijo, sin pérdidas realizadas intradía): de acuerdo, es una cota del día limpio. La garantía en el bot la dan `_reserva` + el margen realizado, cubiertos por pruebas.

## Qué revisar
1. Que con A1 la suma posición + pendiente nunca pase del margen proyectado, en los dos órdenes de entrada.
2. Que `lotes_pendientes_otras` no cuente las pendientes de la propia estrategia (el par OCO del ORB).
3. Que `setUp` no esconda un error real de alguna prueba que antes dependía del estado de otra.
