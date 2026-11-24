# HANDOFF para Neon — Correcciones de AUDIT_010 (Bloque 5)

Audita el commit 1fbeb1b (rama audit-010, ya en main) contra 9043315. Son las correcciones de tu AUDIT_010 (RECHAZADO). Claude verificó cada hallazgo contra el código, corrigió los reales y agregó 10 pruebas que fallan con el código anterior y pasan con el nuevo (61 en total, también aisladas). Reglas de las estrategias: sin cambios.

## Qué se hizo con cada hallazgo
| # | Veredicto de Claude | Cambio |
|---|---|---|
| A1 CRÍTICO | Real (las dos cosas) | `riesgo_despues()` + `_reserva()`: la posición que entró antes deja reservado para la que entra después (o para la orden pendiente de mayor riesgo de la otra estrategia) lo que esta arriesga, máx. `TOPE_MIN_USD` ($500). En `asegurar_tope` (posiciones) y en `tope_stop` (al entrar). Así riesgo_1 + riesgo_2 ≤ margen antes del freno (que ya descuenta el colchón), también con pérdidas realizadas. `tope_stop` reparte con `margen_ftmo(..., solo_realizado=True)` y conserva el bloqueo de entrada con min(balance, equity). |
| A2 ALTO | Real | `partir_dias`: si la primera vela de hoy es posterior a 9:35, no se pasa por `_en_rejilla` (la guardia de `sincronizar` aborta). `velas()`: quita índices duplicados. |
| A3 ALTO | Real | `_ARCHIVOS = threading.Lock()` en `_subir_archivo` (lectura), `guardar_estado` (escritura + `os.replace`) y `log` (escritura). `_hilo_subida`: si `_subir_archivo` devuelve False, `pend = True`. |
| A4 ALTO | 1) y 3) reales; 2) no con datos | 1) `run-name` = «Bot Nasdaq (prueba)» con `prueba=true`; `vigia.decidir` las excluye de `de_hoy`. 3) Última corrida `cancelled` → no relanza (el runner caído del 23-nov terminó en `failure`, no en `cancelled`). 2) Las 14 pruebas recientes duraron 167–195 s (< 240 s); un día sin operar real dura ~3 h (el bot espera hasta el cierre). Con 1) las pruebas ya no cuentan. Se deja 240 s. |
| A5 MEDIO | Real | `cargar_salidas_prot(hoy)` al arrancar: reconstruye `_SALIDA_PROT` desde la bitácora (filas `salida` con motivo «stop de seguridad:» o «el precio ya está en el piso asegurado»). Solo se marca si `cerrar()` devolvió True. Se eligió la bitácora y no el estado para no pisar el `est` que `main` tiene en memoria. |
| A6 MEDIO | Real | `sacudida`: si hay sacudida, marca la vela solo si `cerrar()` confirmó; si no, `return` y la misma vela reintenta en el próximo ciclo. |
| A7 MEDIO | Real (solo Lucid) | `f=(n_v / n_mnq) if n_mnq else 0.0`. |
| A8 MEDIO | Real | `calcular_desfase`: excluye `FERIADOS` y descarta `srv_menos_utc` si se aleja más de 3 h de NY+7 h (deja +7 h y avisa). |
| A9 BAJO | Real en pruebas | Login ficticio 12345678. `estado_nasdaq.json` se migra solo al hash en la próxima corrida (`main`, líneas «estado viejo con el login a la vista»). El login seguirá en el historial de git (es una demo; el password nunca estuvo en el repo). |
| A10 BAJO | Real | Prueba aislada (tick simulado). El guardado hace `git clean -fdq contexto/` antes del pull. `fail-fast: false` con dos piernas: hoy FTMO se salta por la guardia de IP; se revisará al montar el servidor en México. |

## Respuesta a tu pregunta (A1)
Medido en 8 años (`investigacion/scripts/c1e.py`, modelo de `c1b.py` con el tope aplicado a todas las operaciones; resultado base 6 MNQ):

| Variante | Efecto | Peor riesgo con el bot caído |
|---|---|---|
| C1 anterior (piso $500, la primera no cede) | −1.7% | $5,000 (= límite diario) |
| **Elegida: la primera cede la reserva (también ante la pendiente)** | **−1.3%** | **$4,600 (margen − colchón)** |
| Bloquear la 2.ª si no cabe (C1 estricto) | −7.3% | $4,600 |
| Bajar el tope a $4,000 para todas | −4.4% | $4,600 |

## Qué revisar
1. Que `_reserva` nunca deje riesgo_1 + riesgo_2 > margen antes del freno (posición+posición y posición+pendiente), incluido el orden de procesamiento en `asegurar_tope` (converge en ≤ 1 ciclo de 2 s).
2. Que `tope_stop(..., clave=...)` no reserve contra las pendientes de su propia estrategia.
3. Que el candado no pueda bloquear (no se toma dentro de otro tramo con el candado; `marcar_subida` queda fuera).
4. Que `cargar_salidas_prot` no bloquee entradas de días anteriores ni de la otra estrategia.

Cuenta FTMO Swing (sin restricción de noticias); 6 MNQ en el reto y 4 en la fondeada; tope 2× por estrategia; ORB con órdenes stop; reglas de las estrategias congeladas; stop de seguridad $4,500 / ruido 1%.
