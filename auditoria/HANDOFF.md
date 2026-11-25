# HANDOFF para Neon — AUDIT_014: ¿el backtest está sobreajustado?

Esta auditoría es distinta a las anteriores: no revisas un diff, sino **la validez estadística de todo el backtest** antes de poner dinero real (FTMO 100K, ~1-dic-2026).
Pregunta de Matheus: «¿Nuestro backtest está sobreajustado o es fuera de muestra?». Sé escéptico: tu trabajo es intentar **romper** los resultados, no confirmarlos.

**Reglas para ti:**
- No edites nada dentro de `bot-nasdaq\`. Si escribes scripts, ponlos en una carpeta aparte (por ejemplo `..\neon_sobreajuste\`) y trabaja sobre una **copia** del repo.
- Todo número que reportes debe salir de un cálculo que hayas corrido o de un archivo citado (archivo:línea). Si no pudiste correr algo, dilo y explica por qué.
- Separa lo que **mediste** de lo que **opinas**.

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
- **En vivo:** solo desde el 17-nov-2026 (`bitacora_nasdaq.csv`, Tickmill demo, ~1 MNQ). Es demasiado poco para concluir algo, pero sirve para medir si el bot hace lo mismo que la simulación.

## 3. Lo que Claude reconoce de antemano (verifícalo, no lo aceptes)
- **No hay un período de reserva (holdout) que nunca se haya mirado.** Todas las capas se eligieron viendo los 8 años completos. Las «mitades» son una revisión de consistencia, no datos fuera de muestra.
- Se probaron **muchas** ideas y se descartaron (ver `investigacion/scripts/` (~116 scripts) y la lista de abajo). Eso aumenta el riesgo de que las capas que quedaron sean suerte.
- Ideas descartadas (parcial): EMAs 4/8/16 y EMA 200, rebote vs ruptura con 13 indicadores, BPR estilo ICT (30 variantes), modelo de 31 rasgos (fuera de muestra 2021–26: $48 → $36/día), escaneo de 145 factores (solo «caída de ayer» con |t| > 3.4), amplitud de mercado, DIX, GEX, curva VIX, flujos obligados, Stocktwits, S&P/Dow/oro, rangos de 45–90 min, VWAP, gaps, escalones, rachas, operar de noche, Londres (ORB y filtro).
- Regla interna para aceptar una capa: |t| > ~3 **o** las dos mitades en el mismo sentido, y preferir mesetas a picos. Varias capas activas tienen t < 2.

## 4. Qué te pido

### Parte A — Revisión de método (sin correr código)
1. **Look-ahead:** revisa `investigacion/scripts/bt.py`, `bt2.py`, `agresivo.py`, `reglas.py` y `calendario.py`. ¿Alguna señal usa una vela que aún no cerró, el cierre del día, o datos publicados después (COT, VIX, resultados de empresas, calendario Fed)? Cita archivo:línea.
2. **Costos y ejecución:** ¿1.5/2 pts son realistas para órdenes stop en la ruptura (deslizamiento en velas rápidas)? ¿Cómo trata la simulación las velas que tocan entrada y stop a la vez?
3. **Grados de libertad:** cuenta los parámetros elegidos con los datos (rango 30 min, BE $150, sacudida 0.6%, stop 1%, horarios del ruido, multiplicadores 0.5/1.5, umbrales de caída/volatilidad, etc.) y estima el número efectivo de pruebas (N) con la lista del punto 3.
4. **Coherencia simulación ↔ bot:** ¿`estrategias.py`/`bot_nasdaq.py` hacen lo mismo que la simulación?

### Parte B — Pruebas independientes (si puedes correr Python)
Cómo correr la simulación: copia el repo a una carpeta temporal; dentro de `investigacion\scripts\` copia `..\..\historia_nas_dukascopy.csv`, `..\..\historia_ustec_m5.csv` y la carpeta `..\..\extra\`; luego `python reglas.py` (tarda unos minutos). Si algo falla, escribe tu propio backtest mínimo de las dos estrategias base con `historia_nas_dukascopy.csv`.
1. **Base vs completo:** $/día y Sharpe de las dos estrategias **sin ninguna capa** vs el bot completo, por mitades y por año. ¿Cuánto del resultado viene de las capas elegidas con los datos?
2. **Walk-forward:** elige los parámetros principales (minutos del rango, nivel de break even, sacudida, horarios del ruido) **solo con 2019–2022** y mide 2023–2026 con esos parámetros congelados. Haz lo mismo al revés (entrenar 2023–26, probar 2019–22). Reporta la caída de rendimiento.
3. **Deflated Sharpe Ratio** (Bailey y López de Prado 2014) del bot completo con N = 50, 200 y 500 pruebas. Si puedes, **PBO por CSCV** (probabilidad de sobreajuste en el backtest) con las variantes de capas activadas/desactivadas.
4. **Sensibilidad:** costos ×2, parámetros ±20% (¿meseta o pico?), quitando el mejor 1% y 5% de los días, y con bootstrap por bloques de 20 días (intervalo de confianza del $/día).
5. **Bróker real vs Dukascopy:** corre las estrategias base sobre `historia_ustec_m5.csv` (jun-2025 → nov-2026) y compara con Dukascopy en las mismas fechas.
6. **Vivo vs simulación:** compara las operaciones de `bitacora_nasdaq.csv` (desde el 17-nov) contra lo que la simulación habría hecho esos mismos días (entradas, salidas, resultado).

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
