# Bot Nasdaq (demo)

Opera en una cuenta **demo** de Tickmill (MT5) el CFD del Nasdaq-100 (`USTEC`) con las dos estrategias de la prueba MNQ:

- **Rango de 30 min (ORB30):** la primera ruptura del rango de 9:30–10:00 (Nueva York) entra; el stop queda en el otro lado del rango.
- **Zona de ruido** (Zarattini, Aziz y Barbon 2024): revisa a las :00 y :30 desde las 10:00.

Opera 2 lotes de USTEC por estrategia (≈ 1 MNQ, US$2 por punto) y cierra todo a las 15:55 de Nueva York (2:55 pm en CDMX en invierno).

- `estrategias.py`: las reglas, iguales al indicador «MNQ señales» y al juez diario.
- `bot_nasdaq.py`: conecta con MT5 y deja la cuenta igual que el modelo.
- `bitacora_nasdaq.csv`: todo lo que hizo.
- Resumen diario: issue «📊 Update diario del bot Nasdaq».

Lo lanza cron-job.org: 9:45 y 12:40 de Nueva York, de lunes a viernes. Solo funciona en cuentas demo.
