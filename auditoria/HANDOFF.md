# HANDOFF para Neon — AUDIT_013: servidor propio en Azure + correcciones de AUDIT_012

Audita `git diff eecc6c7..HEAD -- '*.py' .github/ infra/` (todo ya en main). Son dos bloques:
1. Correcciones de tu AUDIT_012 (APROBADO).
2. Paso de la cuenta FTMO a un servidor propio en Azure (México), porque FTMO prohíbe entrar a MetaTrader desde IP de EE. UU. y los runners de GitHub están en EE. UU.

Las reglas de las estrategias no cambiaron, ni el bot de 100K en Tickmill.

## Bloque 1: correcciones de AUDIT_012 (merge f9d19f7)
- **A1:** `lotes_relleno` respeta `volume_min` y `volume_max` (100K sin cambios).
- **A2:** `s50_dia(e, hoy)` crea `ftmo_50k` si no existe.
- **A3:** `s50_intradia(est, R, colchon)` usa `max(0.4% × 50K, colchon_freno(sym) × 0.5)`.
- **Pregunta 2:** `--prueba` imprime los MNQ y lotes de `lotes_del_dia`.
- Prueba: `test_audit012_relleno_minimo_sombra_sin_historial_y_colchon`. 69 pruebas, todas también aisladas.
- **Tu pregunta 1:** en el servidor de FTMO, US100.cash = 2 lotes por MNQ, confirmado en vivo el 24-nov.

## Bloque 2: servidor propio
**Infraestructura** (fuera del repo, para contexto):
- VM Windows Server 2022, Standard_B2s_v2, región Mexico Central (IP de México).
- Runner de GitHub `azure-mx` con etiquetas `self-hosted, ftmo-mx`.
- Logic Apps con identidad administrada: encienden la VM lun–vie a las 9:10 ET y la apagan (*deallocate*) a las 16:30 ET.
- El repo es público: GitHub pide aprobación para workflows de pull requests de colaboradores externos.

**Archivos:**
- `.github/workflows/bot_ftmo.yml` (nuevo):
  - Flujo propio con `concurrency: bot-ftmo` y `runs-on: [self-hosted, ftmo-mx]`.
  - Guardia de IP (falla en rojo si es EE. UU. o desconocida).
  - Instala MT5 de FTMO solo si no existe (busca `terminal64.exe` en una carpeta con «FTMO»).
  - Abre MT5 con un .ini temporal que se borra en `finally`.
  - Contexto del repo o `contexto.py`.
  - Cierra `terminal64` al terminar.
  - Guarda `bitacora_nasdaq_ftmo.csv` y `estado_nasdaq_ftmo.json` con el mismo bucle de reintentos.
  - Variables opcionales `vars.FTMO_MNQ`, `vars.FTMO_ETAPA`, `vars.FTMO_INICIAL` (por defecto 6 / reto / 100000).
- `.github/workflows/bot_nasdaq.yml`:
  - Quita la pierna `ftmo` de la matriz.
  - Agrega el trabajo `lanzar_ftmo` (`needs: contexto`, `if: always()`, `continue-on-error`), que hace `gh workflow run bot_ftmo.yml -f prueba=…`.
  - `permissions: actions: write`.
  - **Objetivo:** si la VM está apagada o caída, solo espera el flujo FTMO; el de Tickmill no se bloquea por la concurrencia `bot-nasdaq`.
- `infra/preparar_vm.ps1` (se corre una vez dentro de la VM):
  - Instala Git para Windows (bash en el PATH) y PowerShell 7.
  - Energía siempre encendida; Windows Update sin reinicios con sesión abierta y horario activo 6–22.
  - Registra el runner (token pedido con `Read-Host`).
  - Tarea programada al iniciar sesión que corre `run.cmd`, interactiva y elevada: MT5 por Python necesita una sesión de Windows.
  - Inicio de sesión automático con Autologon de Sysinternals (contraseña pedida con `Read-Host -AsSecureString`, guardada como secreto LSA).
  - Solo ASCII.

**Verificado en vivo (24-nov, prueba gratis FTMO …731):**
- IP MX, conexión OK, servidor a +7 h de NY.
- Apagar → encender con los Logic Apps → el runner volvió solo → prueba OK.

## Qué revisar
1. **¿Puede el flujo FTMO operar dos veces a la vez o pisar el estado?**
   - Concurrencia `bot-ftmo` + vigía (el vigía solo relanza `bot_nasdaq.yml`, que a su vez lanza `bot_ftmo.yml`).
   - ¿Qué pasa si el relevo de las 12:40 encuentra todavía corriendo el tramo de la mañana?
2. **Seguridad con repo público + runner propio:**
   - ¿Algún disparador (`pull_request`, `workflow_run`, etc.) en cualquier workflow podría ejecutar código de un fork en `ftmo-mx`?
   - ¿Queda la contraseña de FTMO en disco o en logs?
3. **Robustez del runner persistente:**
   - `_work` reutilizado entre corridas (checkout limpio, `git clean`).
   - `pip` y `setup-python` en un runner propio.
   - `Stop-Process terminal64` (hoy hay una sola cuenta).
   - ¿Qué pasa si la VM se apaga a las 16:30 ET con un trabajo todavía corriendo?
4. **`lanzar_ftmo`:**
   - Que falle sin afectar al trabajo `operar` de Tickmill.
   - Que `PRUEBA` llegue bien como texto `true`/`false`.
5. **`preparar_vm.ps1`:** errores que dejen la VM a medias, o riesgos (Autologon, tarea elevada).
6. **Huecos:**
   - El vigía no detecta si solo cae el flujo FTMO.
   - No hay aviso si la VM no prende.
   - Propón la solución más simple.
