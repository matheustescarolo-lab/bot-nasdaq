# HANDOFF para Neon — Bloque 4 (auditoría del proyecto, ya subido a main el 23-nov)

Audita los commits 3886cdd..9043315 (rama bloque-auditoria, ya en main con el merge 91461b6). Matheus decidió subirlo sin esperar la auditoría por la caída del runner del 23-nov; esta revisión es posterior.

## Incidente
El 23-nov el runner hospedado de GitHub perdió la conexión a las 14:36 NY a mitad del tramo de la tarde («The hosted runner lost communication with the server»). Además el paso de guardado fallaba en silencio desde el 20-nov.

## Cambios
- **Vigía** (vigia.yml + vigia.py): workflow_run al terminar el bot + schedule */15 13-21 UTC L-V. Relanza (gh workflow run … -f origen=vigia) solo si NY está entre 9:50 y 15:45 (12:45 en medio día), no es feriado y NO hay ninguna corrida activa o en espera. Tope de 4 por día; no relanza si la última terminó bien en < 4 min.
- **A1:** el guardado de bitácora/estado y el de contexto usan ok=1 + rebase --abort + exit 1 si no se subió.
- **A3:** SUBIR_EN_VIVO sube estado y bitácora a main con la API de contenidos (hilo en segundo plano, ≤ cada 60 s, reintenta con 409/422; solo en Actions y no en prueba).
- **C1:** _tope_compartido(): la posición que entra después recibe min(tope, max($500, margen − riesgo de las abiertas hasta su stop desde su entrada; 0 si está en break even o mejor)). La que ya estaba no se aprieta por la segunda (antes_de=(time, ticket)). Medido en 8 años: −1.0% de ganancia; peor combinado con bot caído ≈ $5,000 (topes que no dejan entrar: −6.4%).
- **M1:** salidas por protección del bot quedan en _SALIDA_PROT y salio_por_stop() espera al siguiente chequeo.
- **M2:** medio día no opera (la simulación solo usa días con ≥ 70 velas).
- **M3:** ORB «activo» sin pendiente solo entra a mercado a ≤ 0.1% del nivel.
- **M4:** la entrada de la zona de ruido anota el desvío contra el cierre del chequeo.
- **B1:** 0 MNQ permitido (como round() en la simulación): no abre esa estrategia, pero sigue administrando lo abierto (commit 9043315).
- **B3:** partir_dias() pone cada día en la rejilla 9:30–15:55 y rellena velas faltantes con el último cierre.
- **B4:** desfase en horas enteras y solo con mercado abierto.
- **B6:** estado dañado → EstadoDanado y no opera; en la cuenta ftmo la base es siempre FTMO_INICIAL.
- **B7:** cerrar_viejas() cancela pendientes de días anteriores.
- **B8:** la sacudida revisa todas las velas cerradas desde la entrada.
- **B9:** el estado guarda id_cuenta(login) (sha256) y los logs solo los últimos 3 dígitos.
- 51 pruebas en verde; días completos con MT5 simulado sin errores; prueba de conexión con Tickmill OK.

## Decisiones ya tomadas (no reabrir)
Cuenta FTMO Swing (sin restricción de noticias); 6 MNQ en el reto y 4 en la fondeada; tope 2× por estrategia; el ORB entra con órdenes stop; reglas de las estrategias congeladas; stop de seguridad $4,500 / ruido 1% (aprobado en AUDIT_005–009 de la carpeta local).

## Pide
Errores en el vigía (bucles, cancelar tramos, horarios), en la subida en vivo (conflictos con el commit final), en C1 y en los cambios M1–B9; casos borde; pruebas que falten.
