# Bot Nasdaq (demo)

Opera en una cuenta **demo** de Tickmill (MT5) el CFD del Nasdaq-100 (`USTEC`) con las dos estrategias de la prueba MNQ:

- **Rango de 30 min (ORB30):** la primera ruptura del rango de 9:30–10:00 (Nueva York) entra; el stop queda en el otro lado del rango.
- **Zona de ruido** (Zarattini, Aziz y Barbon 2024): revisa a las :00 y :30 desde las 10:00.

Opera 2 lotes de USTEC por estrategia (≈ 1 MNQ, US$2 por punto) y cierra todo a las 15:55 de Nueva York (2:55 pm en CDMX en invierno).

Protección de ganancias (desde el 18-nov-2026): rango de 30 min con break even al ir +US$150; zona de ruido con escalera (a +US$200 asegura +US$100 y sube el piso de US$100 en US$100). El stop se mueve en el servidor y nunca baja.

- `estrategias.py`: las reglas, iguales al indicador «MNQ señales» y al juez diario.
- `bot_nasdaq.py`: conecta con MT5 y deja la cuenta igual que el modelo.
- `bitacora_nasdaq.csv`: todo lo que hizo.
- Resumen diario: issue «📊 Update diario del bot Nasdaq».

Lo lanza cron-job.org: 9:45 y 12:40 de Nueva York, de lunes a viernes. Solo funciona en cuentas demo.

**Modo examen (desde el 18-nov-2026):** 6 MNQ por estrategia (12 lotes de USTEC) y meta diaria de +US$1,550: al llegar, cierra todo y no opera más ese día. Simula el examen de Lucid Flex 50K (meta +US$3,000, pérdida máxima US$2,000 al cierre que se fija en +US$100 al pasar +US$2,100, consistencia del 50 %) y lleva la cuenta en `estado_nasdaq.json`. Se cambia con las variables `BOT_MNQ` y `BOT_META_DIARIA`.
