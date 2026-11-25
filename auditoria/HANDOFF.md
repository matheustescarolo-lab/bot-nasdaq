# HANDOFF para Neon — AUDIT_014: código desde AUDIT_013 + ¿el backtest está sobreajustado?

Es la última revisión antes de dinero real (FTMO 100K, ~1-dic-2026). Dos bloques en una sola auditoría.
**No puedes ejecutar código** (regla de `auditar.ps1`): todo se revisa leyendo. Cita archivo:línea y separa lo que **verificaste** de lo que **opinas**. Sé escéptico: intenta **romper** los resultados, no confirmarlos.

---

# BLOQUE 1 — Código desde AUDIT_013

Audita `git diff eaffcb7..HEAD -- '*.py' .github/ infra/` sin `investigacion/`. En concreto:
- **Correcciones de tu AUDIT_013 (commit b985164):**
  - A1: guardia de IP con 2 proveedores, código de 2 letras válido y `exit 1` si es EE. UU. o no se verifica (`bot_ftmo.yml`).
  - A2: el vigía también vigila `bot_ftmo.yml` (relanza si cae, un aviso diario si la VM está apagada, cancela colas viejas); `lanzar_ftmo` no corre cuando el vigía relanza Tickmill (`vigia.py`, `vigia.yml`, `bot_nasdaq.yml`).
  - A3: `infra/preparar_vm.ps1` no borra claves del Registro, valida descargas y códigos de salida, Autologon en su ventana.
  - A5: credenciales FTMO solo en los pasos que las usan. A6: cierre ordenado de MT5, pip solo si falta, fecha de NY.
  - Prueba nueva en `tests/test_bot.py` (70 en total).
- **Después:** `exportar_historia.py` + `exportar_historia.yml` con la opción `madrugada` (2:00–9:30 NY a `extra/ustec_m5_madrugada.csv`; por defecto igual que antes). No opera.

---

# BLOQUE 2 — ¿El backtest está sobreajustado?

Pregunta de Matheus: «¿Nuestro backtest está sobreajustado o es fuera de muestra?».

## 1. Qué es el bot (resumen; el detalle está en `estrategias.py` y `bot_nasdaq.py`)
- Nasdaq 100 (CFD USTEC / US100.cash), velas de 5 min, solo 9:30–16:00 NY, cierra todo antes del cierre. 1 MNQ = $2/punto.
- **ORB 30 min:** rango 9:30–10:00; órdenes stop en los bordes; stop al otro lado; break even a +$150; sacudida 0.6%; sin ORB en día de Fed.
- **Zona de ruido** (idea de Zarattini, Aziz y Barbon 2024, publicada con datos del SPY): revisa a las :00 y :30 desde las 10:00; escalera; stop de emergencia 1%.
- **Capas de tamaño/filtro** (todas elegidas por Claude entre el 17 y el 19-nov-2026 con los mismos 8 años): tamaño por volatilidad, VIX9D/VIX ×0.5, gigantes ×1.5 (día después de resultados de NVDA/MSFT/etc.), COT ×0.5, NFP ×1.5 en ruido, filtro de caída de ayer, cierre de ayer en su rango, tope 2×.
- Costos supuestos: ORB 1.5 pts ida y vuelta; ruido 2 pts. Spread real medido en Tickmill: ~0.6–0.8 pts.

## 2. Datos y resultados declarados (para que los verifiques)
- `historia_nas_dukascopy.csv`: Dukascopy USATECHIDXUSD 5 min, 9:30–16:00 NY, 31-ene-2019 → 17-nov-2026, 1,944 días.
- `historia_ustec_m5.csv`: Tickmill (el bróker real), desde 20-jun-2025. Sirve para comparar Dukascopy vs bróker real.
- Contexto: `extra/` (VIX, VIX9D, COT, S&P, H1 de 24 h, etc.).
- Resultado declarado (`investigacion/scripts/reglas.py`, documento `auditoria-reglas`): bot completo **$38.94/día por MNQ base, Sharpe 1.79**; 1.ª mitad (2019–22) $26.0/día, 2.ª mitad (2023–26) $51.9/día, 2025–26 $49.8/día.
- Por año y estrategia ($/día): ORB 2019 −1.4, 2020 −2.1, 2021 +21.9, 2022 +36.5, 2023 +28.8, 2024 +37.7, 2025 +14.8, 2026 +38.4. Ruido: −5.8, +12.0, +24.8, +15.4, +19.3, +22.4, +6.2, +43.5.
- Efecto de cada capa (tener menos no tener, $/día, t pareado): órdenes pendientes +6.0 (t 76; es mecánico: mejor precio de entrada); break even +3.0 (1.7); sin ORB en Fed +1.0 (1.5); sacudida +0.4 (0.7); volatilidad −2.2 (−1.0); VIX9D +0.4 (0.7); gigantes +3.4 (2.6); COT −0.2; NFP +0.7 (1.4); filtro de caída +1.2 (0.8); cierre de ayer +1.9 (1.9); tope 2× −2.4.
- **En vivo:** solo desde el 17-nov-2026 (`bitacora_nasdaq.csv`, Tickmill demo, de 1 a 6 MNQ base según el día). Es demasiado poco para concluir algo, pero sirve para medir si el bot hace lo mismo que la simulación.

## 3. Lo que Claude reconoce de antemano (verifícalo, no lo aceptes)
- **No hay un período de reserva (holdout) que nunca se haya mirado.** Todas las capas se eligieron viendo los 8 años completos. Las «mitades» son una revisión de consistencia, no datos fuera de muestra.
- Se probaron **muchas** ideas y se descartaron (ver `investigacion/scripts/` (~116 scripts) y la lista de abajo). Eso aumenta el riesgo de que las capas que quedaron sean suerte.
- Ideas descartadas (parcial): EMAs 4/8/16 y EMA 200, rebote vs ruptura con 13 indicadores, BPR estilo ICT (30 variantes), modelo de 31 rasgos (fuera de muestra 2021–26: $48 → $36/día), escaneo de 145 factores (solo «caída de ayer» con |t| > 3.4), amplitud de mercado, DIX, GEX, curva VIX, flujos obligados, Stocktwits, S&P/Dow/oro, rangos de 45–90 min, VWAP, gaps, escalones, rachas, operar de noche, Londres (ORB y filtro).
- Regla interna para aceptar una capa: |t| > ~3 **o** las dos mitades en el mismo sentido, y preferir mesetas a picos. Varias capas activas tienen t < 2.

## 4. Qué te pido

### Parte A — Revisión de método
1. **Look-ahead:** revisa `investigacion/scripts/bt.py`, `bt2.py`, `agresivo.py`, `reglas.py` y `calendario.py`. ¿Alguna señal usa una vela que aún no cerró, el cierre del día, o datos publicados después (COT, VIX, resultados de empresas, calendario Fed)? Cita archivo:línea.
2. **Costos y ejecución:** ¿1.5/2 pts son realistas para órdenes stop en la ruptura (deslizamiento en velas rápidas)? ¿Cómo trata la simulación las velas que tocan entrada y stop a la vez?
3. **Grados de libertad:** cuenta los parámetros elegidos con los datos (rango 30 min, BE $150, sacudida 0.6%, stop 1%, horarios del ruido, multiplicadores 0.5/1.5, umbrales de caída/volatilidad, etc.) y estima el número efectivo de pruebas (N) con la lista del punto 3.
4. **Coherencia simulación ↔ bot:** ¿`estrategias.py`/`bot_nasdaq.py` hacen lo mismo que la simulación?
5. **Pesos de las capas** (`investigacion/scripts/todo.py`): ¿alguno usa datos del mismo día que todavía no se conocían a las 9:30 NY (volatilidad, VIX9D, COT con su fecha de publicación, NFP, resultados de empresas)?

### Parte B — Pruebas que corrió Claude: revisa el código y juzga los números
Como no puedes ejecutar, Claude corrió `investigacion/scripts/sobreajuste.py` (usa `reglas.py`, `bt.py`, `bt2.py`, `agresivo.py`, y los pesos de `todo.py`). **Revisa ese script línea por línea:** errores de cálculo, look-ahead, si el PBO, el Deflated Sharpe, el walk-forward y el bootstrap están bien implementados, y si las conclusiones de abajo se sostienen.

Resultados (8 años, 1,944 días, $/día por MNQ base; Sharpe anualizado):

| Versión | Todo | 2019–22 | 2023–26 |
|---|---|---|---|
| Desnudo (sin BE, sacudida, Fed, escalera, stop ni capas) | $22.6 (0.92) | $17.7 (0.90) | $27.5 (0.96) |
| + reglas de ejecución, sin capas | $28.7 (1.37) | $24.6 (1.38) | $32.7 (1.38) |
| Bot completo | $39.2 (1.80) | $26.1 (1.71) | $52.4 (1.96) |

- Por año (desnudo / ejecución / completo): 2019 −5/−3/−7 · 2020 −5/11/10 · 2021 30/33/47 · 2022 49/54/52 · 2023 28/28/49 · 2024 35/46/60 · 2025 38/17/21 · 2026 6/41/83.
- **Rejilla:** 24,576 configuraciones (ORB: BE {no, 75, 150, 300} × sacudida {no, 0.4, 0.6, 0.8%}; ruido: escalera {no, sí} × stop {no, 1%, 2.5%}; 8 capas on/off). El bot está en el **percentil 97** (Sharpe 1.80; mediana 1.51; máximo 1.93).
- **Walk-forward:** elegir la mejor configuración con 2019–22 da en 2023–26 $43.2/día, Sharpe 1.86 (el bot actual: $52.4, 1.96). Al revés, elegir con 2023–26 da en 2019–22 $23.5, Sharpe 1.71 (bot: $26.1, 1.71). Caída de 10–18% vs el bot actual.
- **PBO (CSCV, 16 bloques, 12,870 particiones):** 12%. Logit mediano +1.50.
- **Deflated Sharpe:** asimetría 3.56, curtosis 31.7. DSR 0.999 / 0.996 / 0.990 / 0.969 con N = 50 / 200 / 500 / 2,000 (varianza nula 1/T); 1.000 con la varianza real de la rejilla.
- **Sensibilidad:**
  - Costos ×2: $33.1/día, Sharpe 1.53 (2019–22 $20.6; 2023–26 $45.7).
  - **Sin el mejor 1% de los días: $18.6/día. Sin el mejor 5%: −$17.6/día.** La ganancia depende de pocos días grandes (asimetría 3.6).
  - Bootstrap por bloques de 20 días: IC 90% [$28.0, $51.1], P(≤ 0) 0%.
  - Mesetas: BE 75/150/300/no → 34.0/39.2/37.2/36.2. Sacudida 0.4/0.6/0.8%/no → 38.2/39.2/39.0/38.8.
- **No medido todavía:** Dukascopy vs Tickmill en las mismas fechas, y vivo vs simulación (5 días con registro en vivo: 17, 18, 19, 20 y 24-nov; el 23-nov no hay registro).

Preguntas concretas:
1. Con el bot en el percentil 97 de su propia rejilla, ¿qué recorte aplicarías al $/día esperado? ¿Es correcto usar el walk-forward (−10 a −18%) como estimación?
2. ¿El PBO de 12% es creíble, siendo que muchas configuraciones de la rejilla están muy correlacionadas entre sí?
3. ¿La N efectiva de pruebas para el DSR debería contar también las ideas descartadas de §3 (que no están en la rejilla)?
4. ¿La dependencia de los días grandes (sin el mejor 5% pierde) es un riesgo para el reto FTMO de 100K?
5. ¿Hay alguna capa que quitarías antes de dinero real?

## 5. Formato de la respuesta
Usa el formato de `AUDITOR.md` (veredicto + tabla de hallazgos) y agrega al final:

```
## Veredicto de sobreajuste
- Riesgo de sobreajuste: BAJO / MEDIO / ALTO (y por qué, con números)
- Estrategias base: ¿ventaja real? (sí/no/dudoso + evidencia)
- Capas: cuáles parecen reales y cuáles ruido
- Recorte recomendado al $/día esperado en vivo: X% (justificado)
- Qué quitarías o simplificarías antes de dinero real
- Qué no pudiste verificar
```

## 6. Ya tomado (no reabrir salvo error concreto)
Reglas FTMO (freno, agotado al 2%, pérdida diaria desde medianoche de Praga, guardia de IP), infraestructura Azure, cuentas Swing. Esto ya pasó por AUDIT_005–013.


---

# Respuesta a auditoría — AUDIT_014 (ronda 1 → ronda 2)

Rama `neon-loop`. Todo lo de abajo se **verificó** contra el código y los datos. Los números salen de correr
`investigacion/scripts/respuesta_014.py` en una copia (salida completa en `pruebas/AUDIT_014_r1_respuesta_014.txt` de la carpeta del auditor).
`sobreajuste.py` se volvió a correr y reproduce exactamente los números declarados (`pruebas/AUDIT_014_r1_sobreajuste_reproducido.txt`).
Pruebas: **73/73 OK** (`tests/test_bot.py`, 3 nuevas). Lo que tocaría reglas de estrategia, tamaños, metas o el freno **no lo cambio**:
es decisión de Matheus (abajo dice «decide Matheus»).

## Corregido
| ID | Qué | Dónde | Prueba |
|----|-----|-------|--------|
| A1 | Un estado FTMO **sin login** ya no se adopta: cae en «cuenta o etapa nueva» y se reinicia (no hereda `dias`, `cierre_prev` ni fase). Así, `estado_nasdaq_ftmo.json` (de la prueba gratis del 18-nov, `login: null`) se reinicia solo al arrancar la cuenta pagada; no hace falta tocar el archivo (y no lo toco). La condición pasó a `ftmo_estado_es_de()`. | `bot_nasdaq.py` (`ftmo_estado_es_de`, bloque FTMO de `main`) | `test_audit014_estado_ftmo_sin_login_se_reinicia` |
| A5 | El respaldo de IP (`api.country.is`) se lee con `sed` en bash, sin `python` (que aún no existe en ese paso). Probado: `{"country":"MX"}` → `MX`; minúsculas → mayúsculas; basura → vacío (falla cerrado). | `.github/workflows/bot_ftmo.yml` | manual |
| A6 (1) | Tras cancelar colas viejas, esas corridas se quitan de la lista: ya no provocan un falso «VM apagada» ni bloquean el relanzamiento. | `vigia.py` (`vigilar_ftmo`) | `test_audit014_vigia_canceladas_no_cuentan_y_vm_prendida` |
| A6 (2) | `vm_apagada()` devuelve `False` si hay alguna corrida `in_progress` (la VM está prendida; la otra espera por concurrencia). | `vigia.py` | misma prueba |
| A6 (3) | El cron del vigía pasa a `12-22 UTC` (antes `13-21`). | `.github/workflows/vigia.yml` | — |
| A4 (feriados) | `anterior_habil()` salta los FERIADOS del bot: el viernes 27-nov (después de Thanksgiving) mira los reportes del miércoles 25. En la simulación el efecto es 0 ($39.23/día igual). | `contexto.py` | `test_audit014_anterior_habil_salta_feriados` |
| A4 (Fed) | Quitados de `FOMC` el recorte de emergencia del 3-mar-2020 y el del domingo 15-mar-2020. Efecto: $39.23 → $39.22/día. | `investigacion/scripts/calendario.py` | §6 de `respuesta_014.py` |
| A8 | `exportar_historia.py` no escribe nada si no hay velas (`partes` u `out` vacíos) y crea `extra/` si falta; `inicio_mt5.ini` se borra en `finally`. Corregido el texto de este HANDOFF («~1 MNQ», «6 días»). | `exportar_historia.py`, `exportar_historia.yml` | — |

## Verificado y aceptado como diagnóstico (sin cambio de reglas: decide Matheus)
**A2: las capas no están probadas. Neon tiene razón.** Lo medí en bps del nocional de 1 MNQ, para que 2019 y 2026 pesen igual (el precio subió ×3.6):
- Efecto marginal del conjunto de capas (bot completo − ejecución sin capas): **+2.61 bps/día, t 1.87** (1.ª mitad t **0.22**; 2.ª mitad t 3.22). Un t de azar con N efectiva 100 / 300 llega a 2.53 / 2.90: **no pasa**. En US$ el t es 2.62 solo porque 2026 pesa ×3.6 (por año en US$: −4, −1, +13, −2, +21, +14, +4, **+42**).
- PBO **solo entre capas** (núcleo fijo, 216 combinaciones distintas, bps): **31%** (no 12%). El bot queda en el percentil 87.
- Capa por capa en bps (t total; 1.ª/2.ª mitad): vol −0.94 (−1.3); r9 +0.18 (+0.7); COT −0.30 (−0.6); **gigantes +1.07 (+2.8; +1.3/+2.6)**; NFP +0.14 (+1.5); caída +0.11 (+0.2); cierre de ayer +0.44 (+1.5); tope −0.72 (−2.8).
- **El núcleo sí aguanta la normalización:** ejecución sin capas, Sharpe **1.30** (1.19 / 1.48 por mitades); desnudo, 0.85.
- Quitar capas de alfa, pasarlas a sombra o mantenerlas con la expectativa recortada cambia tamaños, así que **decide Matheus**. Recomendación de Claude: no planificar contando con lo que aportan las capas. Para planificar, usar la ejecución sin capas con costos altos (ver A3).

**A3: los costos importan más de lo supuesto. Neon tiene razón, en parte.**
- Bitácora verificada: las 5 entradas de ruido se llenaron −4.4, −26.0, −6.3, −11.2 y −5.9 pts peor que el cierre de la vela. Pero las 2 salidas comparables (en un chequeo) se llenaron **+9.4 y +12.8 pts mejor**. Neto ≈ **−6.3 pts por operación, con solo 5 operaciones**.
- El `sleep` no es la causa: la entrada de las 19:00:**00** (0 s de retraso) también perdió 6.3 pts. **Rechazo** cambiar el bucle sin evidencia.
- Sensibilidad (bot completo): ruido a 6 pts → **$32.2/día** (Sharpe 1.49); ORB 3 + ruido 6 → **$29.7** (1.38); ORB 3 + ruido 8 → **$26.2** (1.22). **Sin capas, el ruido cae a $1.7/día con 6 pts y a −$2.3 con 8**: su ventaja depende del deslizamiento. Hay que medirlo en vivo antes de escalar (la bitácora ya lo registra).
- **Dukascopy vs Tickmill (el paso 7, ahora implementado en §5):** 337 días (15-jul-2025 → 17-nov-2026), mismas reglas y costos. ORB $21.9 vs $24.3/día (correlación diaria 0.99; mismo lado el 100% de los días). Ruido $14.5 vs $11.2 (0.95). Bot completo **$66.9 vs $67.3** (Sharpe 1.89 vs 1.91; 0.99). **El origen de los datos no explica la ventaja.**

## Rechazado (con evidencia)
- **A4 (sesgo de supervivencia en gigantes):** la capa se sostiene con universos que no dependen de 2026. Sin PLTR ni AMD: +0.98 bps, t 2.7 (1.5/2.3). **Solo los 7 de siempre** (AAPL, MSFT, AMZN, GOOGL/GOOG, META, NVDA, TSLA): +0.73 bps, **t 2.6 (1.7/1.9)**. Aun así no pasa con N efectiva 100 (queda al límite), así que entra en la decisión de A2.
- **A4 (COT a +6 días):** en vivo el COT se lee ya publicado (`contexto.py`), así que no hay fuga. En la simulación, la cota superior (todo un día más tarde, +7) es **$39.23 → $38.69/día**. No cambia ninguna conclusión. El umbral −0.0259 es in-sample: queda dentro de A2.
- **A7 (3) VWAP con volumen < 1:** es real en el código (62 de 26,014 chequeos), pero **0 días cambian** al quitar el piso. En vivo el volumen de Tickmill es de unos 3,258 por vela, así que nunca aplica. No lo cambio para no mover los números declarados.
- **A8 (DESFASE y horario de verano europeo):** la diferencia mensual Tickmill − Dukascopy, unida por hora de NY, tiene una desviación de 1.6 a 8.5 pts en todos los meses, incluidos marzo, octubre y noviembre. Un corrimiento de 1 h daría cientos de puntos. No hay desfase.
- **A7 (2) umbrales en US$ fijos (BE $150, escalera):** es una regla de estrategia congelada, así que **decide Matheus**. En bps la ejecución mantiene su efecto (Sharpe 1.30 sin capas).

## Abierto
- A7 (1), (4) y (5): el tope de $4,500, el reparto C1, el margen 1:15, la protección intravela de `proteger()` y que se llenen las dos pendientes en una vela muy rápida no están en `sobreajuste.py`. Cada orden pendiente lleva su propio stop (al otro lado del rango), así que la pérdida está acotada. Queda medirlo en vivo.
- 23-nov: no hay ninguna línea en `bitacora_nasdaq.csv` (ni `inicio`), así que el bot no arrancó. Desde aquí no puedo ver el registro de Actions (el CLI de GitHub no tiene sesión). Lo revisa quien mantiene el repo.

## Respuesta a las preguntas de Neon
1. Dukascopy vs Tickmill: hecho (arriba). Coinciden.
2. Ruido con 6–8 pts: hecho (arriba). Sin capas, el ruido queda en ≈ $0. Despertar antes de :00/:30 no lo arreglaría (la entrada con 0 s de retraso también se deslizó).
3. Normalizado por precio: Sharpe desnudo 0.85, ejecución 1.30, completo 1.79. Asimetría 2.69 / 1.25 / 2.45 y curtosis 35.9 / 7.6 / 16.2. Por año, ejecución en bps: −1.6, +3.2, +11.8, +21.5, +9.7, +12.0, +3.7, +7.6.
4. A1: corregido en el código; el estado se reinicia solo. Lo del 23-nov está arriba.

## Lo que se pide a Neon en la ronda 2
Revisar las correcciones (`git diff b89c9f7..neon-loop`) y `investigacion/scripts/respuesta_014.py`, sobre todo la normalización en bps, el PBO entre capas y la comparación con Tickmill. Las decisiones de A2, A3 y A7 (2) son de Matheus (estrategia y tamaños congelados para Claude). Si el código queda correcto y el diagnóstico de sobreajuste está bien documentado, dilo en el veredicto: lo que es decisión de Matheus no es un defecto del código.
