# Stop de seguridad en el servidor (23-nov-2026)

**Pregunta:** si el bot se cae con una posición abierta, solo protegen los stops del servidor. ¿Se pueden acercar para que quepan en los límites de FTMO sin cambiar el resultado?

## Datos y método
- Nasdaq-100 en velas de 5 min (Dukascopy, `historia_nas_dukascopy.csv`), 2019–2026, 1,805 días.
- Tamaño real del bot en el reto: base 6 MNQ × capas (volatilidad, VIX9D/VIX, gigantes, COT, NFP, posición de ayer, filtro de caída), tope 2×. Montos en US$ al precio actual (27,000) con US$2 por punto por MNQ.
- Señales y salidas idénticas a la simulación validada (`agresivo.py`/`orb_real.py` del laboratorio: ORB con break even y sacudida; zona de ruido con escalera).
- Cuando salta el stop se asume ejecución en el stop **− 2 pts** de deslizamiento. Zona de ruido: el bot vuelve a entrar en el siguiente chequeo :00/:30 si el modelo sigue dentro (igual que `salio_por_stop`).
- No hay parámetro optimizado: el tope sale del límite diario de FTMO (5% = $5,000 menos colchón). Se reportan vecinos y mitades.
- Scripts: `stop_seg.py`, `stop_orb.py`, `stop_reent.py` (dependen de archivos del laboratorio que no están en este repo: `agresivo.py`, `bt2.py`, `orb_real.py`, `calendario.py`, `final_caminos.npz`, `todo_pesos.pkl`).

## Resultados
Zona de ruido (1,501 operaciones; promedio 6.8 MNQ):

| Stop en el servidor | Salta con el bot vivo | Efecto $/día | Peor pérdida si el bot muere |
|---|---|---|---|
| 2.5% (antes) | 0.2% | −0.67 | $16,200 |
| 1% | 2.1% | +1.94 | $6,480 |
| **min(1%, $4,500)** (elegido) | 2.7% | −1.17 (+0.06 con re-entrada) | **$4,500** |
| $2,000 / $2,500 / $3,000 / $3,500 | 12% / 7% / 5% / 3% | −22.5 / −5.4 / −8.7 / −5.8 | $2,000–3,500 |

Referencia: la zona de ruido gana ~$210/día en esta escala. Mitades del periodo con el tope elegido: +4.72 y −4.59 $/día (ruido estadístico alrededor de 0). Peor día de la zona de ruido (sin freno): −$11,544 sin tope, −$9,080 con tope y re-entrada (en vivo el freno FTMO y el tope por margen cortan antes).

Rango de 30 min (1,735 operaciones, $264 por operación):

| Tope desde la entrada | Salta | Efecto por operación |
|---|---|---|
| $3,000 | 5.2% | −$19.3 |
| $4,000 | 1.4% | −$0.18 |
| **$4,500** (elegido) | 1.2% | −$1.84 |

Sin tope, el stop del rango (otro lado del rango) puede perder hasta $10,674; 86 de 1,805 días pasan de $4,000.

## Decisión
- Zona de ruido: stop del servidor a 1% del precio; además ninguna posición puede arriesgar más de $4,500 (4.5% del capital FTMO) ni más que el margen que queda antes del freno.
- Riesgo residual: con las dos posiciones abiertas y el bot caído, hasta ~$9,000 en un día. Bajarlo cuesta ganancia real; la defensa es un servidor confiable.

## Notas de la ronda 2 (AUDIT_006)
- `stop_orb.py` ahora incluye la vela de entrada en el peor movimiento (conservador): resultados idénticos ($4,500: salta 1.2%, −$1.84 por operación).
- Peor caso con el bot caído: el stop puede deslizarse ~2 pts → con 12 lotes, ~$24 sobre los $4,500.
- Re-entradas de la zona de ruido tras el stop: ~40 en 8 años × ~2 pts de costo × ~6.8 MNQ ≈ $0.6/día adicional. No cambia la conclusión.
- Diseño del margen: el stop de cada posición limita la pérdida desde su entrada a min($4,500, margen ya realizado antes del freno). No mira el flotante de la otra posición, así que una caída temporal de una no acerca para siempre el stop de la otra. Para permitir una entrada se usa lo menor entre balance y equity, con el colchón del freno proyectado con los lotes nuevos.
