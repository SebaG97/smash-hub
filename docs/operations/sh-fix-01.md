# SH-FIX-01 — Estado temporal del torneo y cierre del Prode

Fecha: 12/11/2026. Afecta a: [sincronización con start.gg](startgg-sync.md) (ADR-022) y al Prode (ADR-020).

## Diagnóstico

### Center Stage aparecía «En curso» desde el jueves

- La regla de frecuencias (`sync.service.tier`) consideraba en curso a todo torneo con `state = 2` en start.gg. start.gg marca **ACTIVE (2)** a los torneos publicados días antes del inicio, así que Center Stage quedó en «En curso» y se sincronizaba cada 3 minutos desde el 12/11.
- Además, start.gg tiene cargado el inicio el **14/11/2026 a las 19:00 UTC = 16:00 en Asunción**; el inicio real es **14:00 en Asunción = 17:00 UTC**. La copia local guarda exactamente lo que start.gg informa: no hay error de conversión UTC/Paraguay en el hub, el dato de origen está corrido dos horas.

### El Prode cerraba a las 16:00

- `prode_contests.locks_at` se fija **una sola vez**, al abrir el Prode, con el `startAt` del evento de start.gg (o del torneo). Para Center Stage quedó en 19:00 UTC (16:00 en Asunción).
- Ninguna sincronización lo vuelve a escribir: la sincronización de candidatos (`prode.service.sync_candidates`) no toca `locks_at`, y la copia local de start.gg no tiene relación con esa tabla. Solo lo cambian acciones de administradores.
- El backend ya rechazaba pronósticos después del cierre con la hora de la base (`prode.service.save` → `closed()`), sin depender de la web.

## Corrección

1. **El estado oficial de start.gg y el estado temporal quedan separados.** `tier` se decide por la hora: el `state` de start.gg solo cuenta cuando el torneo no tiene hora de inicio (`state = 2` → en curso) o está terminado (`state = 3`). Un torneo futuro marcado ACTIVE se clasifica como lejano, de esta semana o de las próximas 24 h, según falte. El panel muestra los dos: el tramo y el estado de start.gg (`startgg_state` en `GET /api/v1/sync`).
2. **Inicio confirmado por administradores.** `startgg_tournaments.start_confirmed_at` (migración `0023`, aditiva) guarda el inicio real cuando start.gg lo tiene mal. `start_at` sigue siendo el valor de start.gg, intacto; la sincronización no escribe la columna nueva.
   - Con inicio confirmado: el tramo «en curso» empieza exactamente a esa hora (sin el margen de 2 h); las últimas 24 h se cuentan desde ella; la previa, el calendario y los Prodes que se abran después la usan.
   - Sin inicio confirmado: todo sigue igual que antes (inicio de start.gg y margen de 2 h). Ningún otro torneo cambia de comportamiento, salvo que ninguno futuro vuelve a quedar «en curso» por estar ACTIVE en start.gg.
   - No se inventa la hora de fin: se usa la de start.gg (`end_at`) y, si no hubiera, inicio + 1 día como hasta ahora.
3. **Cambio del cierre de un Prode abierto.** `POST /api/v1/prode/contests/{id}/locks-at` con `{"locks_at": "AAAA-MM-DDTHH:MM"}` en hora de Asunción. Solo administradores; solo Prodes abiertos y cuyo cierre no pasó; rechaza horarios ya pasados (para cerrar ya está «Cerrar ahora»). Idempotente: repetir el mismo horario no cambia nada ni duplica la auditoría. Queda en `prode_audit_entries` (`set_locks_at`, antes y después). No toca pronósticos, participantes, candidatos ni resultados.
4. **Horas de Paraguay sin offsets fijos.** `app/core/times.py` convierte «día + hora de Asunción» con la zona IANA `America/Asuncion` (paquete `tzdata`), tanto para el inicio confirmado como para el cierre. La web envía la fecha y la hora tal como se escriben; la conversión la hace la API.

Interfaz: `/admin` → «Sincronización con start.gg» → «Confirmar inicio» (torneo, día, hora de Paraguay; «Usar el de start.gg» lo quita). Previa → pestaña Prode → «Organizadores» → «Cambiar cierre».

## Procedimiento en producción (requiere autorización; no ejecutado)

Plazo: antes del **sábado 14/11 a las 14:00 (Asunción)**.

1. Respaldo: confirmar el respaldo diario del día y la recuperación a un punto en el tiempo, como en SH-SYNC-01.
2. En el job `migrate`, `APPROVED_MIGRATION`: `0022` → `0023` (agrega dos columnas nullable a `startgg_tournaments`). `STARTGG_SYNC_ENABLED` no cambia.
3. Desplegar el commit de SH-FIX-01. Desde ese momento Center Stage deja de figurar «En curso» aunque no se haga el paso 4 (pasa a «Esta semana» según el horario de start.gg).
4. `/admin` → Sincronización → Confirmar inicio: **Center Stage 2026, 14/11/2026, 14:00**. El panel debe mostrar «Inicio 14/11 14:00 (confirmado; start.gg dice 14/11 16:00)» y el tramo «Esta semana» (o «Próximas 24 h» desde el viernes 13/11 14:00).
5. `/previa/center-stage-2026-1` → Prode → Organizadores → Cambiar cierre: **14/11/2026, 14:00**. La cabecera debe decir que cierra el sábado 14/11 a las 14:00. Equivale a `locks_at = 2026-11-14T17:00:00+00:00`.
6. Verificar: el Prode sigue «abierto» con los mismos participantes; `GET /api/v1/prode/tournaments/center-stage-2026-1` → `locks_at` = `2026-11-14T17:00:00+00:00`.

Los pasos 4 y 5 son idempotentes: repetirlos no cambia nada. Para deshacer el 4, «Usar el de start.gg»; para el 5, volver a cambiar el cierre.

**Alternativa si no se pudiera desplegar a tiempo** (con el código actual de producción): la ruta existente `POST /api/v1/prode/contests/{id}/reopen` acepta `{"locks_at": "2026-11-14T17:00:00Z"}` sobre un Prode abierto y solo cambia su cierre (queda auditado como `reopen`). Requiere la sesión de un administrador y el encabezado `X-Requested-With: smashhub`; no tiene botón en la web. Usarla solo con autorización.

## Pruebas

- `tests/test_sync.py`: tramo por hora con ACTIVE en el futuro; Center Stage con inicio confirmado (jueves «week», viernes 14:00 «day», sábado 14:00 «live», fin); cambio de frecuencia a 10 min y a 3 min; torneos sin inicio confirmado sin cambios; conversión UTC ↔ Asunción; confirmación por administradores, idempotencia, y que una sincronización posterior no la pisa.
- `tests/test_prode.py`: cierre movido a las 14:00 de Asunción (17:00 UTC), pronósticos y participantes conservados, idempotencia y auditoría única, rechazo de horarios pasados, de no administradores y de cambios después del cierre; un Prode nuevo toma el inicio confirmado.
- Web: `tests/confirmed-start.test.tsx` (formularios de inicio confirmado y de cierre).
