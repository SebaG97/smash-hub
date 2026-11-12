# Sincronización con start.gg (SH-SYNC-01)

Decisión y alternativas descartadas: [ADR-022](../adr/ADR-022.md). Operación y despliegue: [startgg-sync.md](../operations/startgg-sync.md).

## Antes de esta misión

| Dato | Dónde vivía | Qué pasaba en un reinicio o si start.gg fallaba |
| --- | --- | --- |
| Calendario (`/insights/calendar`) | Memoria, 1 h | Se volvía a pedir; si fallaba, lista vacía con `unavailable` |
| Previa: torneo, evento e inscritos (`/insights/upcoming/<slug>`) | Memoria (`stale`), 15 min | El primer visitante esperaba a start.gg; si fallaba, 502 |
| Pools públicos (`/insights/upcoming/<slug>/pools`) | Memoria (`stale`), 2 min | Igual: espera y 502 |
| Estructura del bracket de la previa y del seeding | Memoria (`stale`), 15 min | ~20 s de espera para un bracket grande; sin bracket si fallaba |
| Pools del organizador (`/seeding/<slug>/pools`) | Memoria, 2 min | Espera y 502 |
| Dataset del seeding (inscritos, sets, mains) | PostgreSQL (`seeding_*`) | Persistía; se vuelve a bajar solo a pedido |
| Resultados de torneos terminados | PostgreSQL (tablas canónicas, CLI) | Persistían |
| Nombres de fases de un evento importado | PostgreSQL (`events.phases`) | Persistían |

## Módulo `app/sync`

| Archivo | Responsabilidad |
| --- | --- |
| `models.py` | Tablas `startgg_*` (ver [esquema](../database/schema.md#migración-0020-adr-022)). |
| `store.py` | Respuesta validada de start.gg → filas: upsert por ID, reactivación, retiro (`active = false`) de lo que una respuesta completa ya no lista, guardas ante respuestas vacías. Sin red. |
| `service.py` | Reclamo de una ejecución (una a la vez), sincronización de un torneo, descubrimiento del calendario, frecuencia según el estado y qué está pendiente. |
| `scheduler.py` | Hilo de la API que cada `STARTGG_SYNC_TICK_SECONDS` ejecuta `service.tick`. |
| `read.py` | Lectores de la copia con la misma forma que devuelven los fetchers de start.gg, para que previas, pools y brackets se armen con el mismo código. Devuelven `None` si esa parte nunca se sincronizó (entonces se consulta start.gg como antes). |
| `router.py` | `/api/v1/sync` para administradores. |

Los documentos GraphQL nuevos (`sync_tournament`, `sync_entrants`, `sync_phase_seeds`, `sync_phase_group_sets`) amplían los existentes con los campos que se guardan (fin, estado y país del torneo; estado del evento; ID de participante, prefijo y país del inscrito; pool, inscripción y origen de cada seed; estado, ganador, marcador e inscripción de cada lado de un set). Las fases se leen con `event_phases`, el mismo documento que ya usaban pools y brackets. Toda paginación de la sincronización usa `StartGGClient.pages`, que exige totales consistentes, IDs únicos y la cantidad exacta: una respuesta incompleta falla en vez de parecer una baja.

## Flujo de una sincronización de torneo

1. `claim`: advisory lock `startgg:sync`; si hay otra ejecución activa, una descarga de seeding o el importador, `SyncBusy` y se reintenta en el próximo tick.
2. `sync_tournament`: torneo y eventos; se confirma.
3. Para el evento principal de singles y los eventos con seeding: inscripciones completas → `store.entrants`; se confirma.
4. Fases (`event_phases`) y los seeds completos de cada fase → `store.phases` (fases, pools y seeds, con su origen en fases posteriores); se confirma.
5. Sets de cada pool de cada fase, con byes y sets de vista previa → `store.sets`; se confirma.
6. Cierre: estado, conteos y advertencias en la ejecución; último intento/éxito, fallas seguidas y próxima sincronización en el torneo.

Cada paso confirma su parte por separado: si falla el paso 3 de un evento, lo anterior queda guardado y la ejecución termina `failed` con su código.

## Qué sigue consultando start.gg en vivo

- Torneos o eventos nunca sincronizados (la primera previa de un torneo que nadie sigue).
- Acciones explícitas de organizadores: actualizar pools (`fresh=true`), adoptar el seeding de start.gg, crear un seeding, descargar sus datos (historial de sets y mains de cada inscrito) y subir seeds.
- Perfiles de jugadores sin datos en el hub (`/insights/startgg-players/<id>`), `/en-vivo` y los nombres de fases de un evento importado (que ya se guardan una vez).

## Lectura

`read.local(engine, lector, …)` abre su propia sesión y, si la base no responde, devuelve `None` para que la página use start.gg en vez de fallar.

- `read.upcoming(slug)`: torneo, evento principal de singles e inscritos activos con un solo participante con Player.id; `synced_at` es el momento de la última copia completa de esas inscripciones. La previa expone `startgg.source` (`local` o `live`) y `startgg.synced_at`.
- `read.calendar()`: torneos que el último descubrimiento completo listó (`in_calendar`), sin los online.
- `read.pools(event_slug)`: el mapa de pools de la primera fase (la de más seeds, como `brackets.first_phase`), armado por `seeding.pools.assemble`, la misma función que usa la lectura en vivo. `found` es `None` si start.gg todavía no armó fases (respuesta sincronizada, no se consulta en vivo). Lo usan `/insights/upcoming/<slug>/pools` y, salvo con `fresh=true`, `/seeding/<slug>/pools` (organizadores). Las parejas de primera ronda (avisos de revancha y compañeros de equipo) salen de los sets copiados.
- `read.structure(event_id)`: la estructura del bracket (pools de la primera fase y fases posteriores con el origen de cada seed), armada por `brackets.service.assemble_structure`, la misma función que la lectura en vivo. La usa `brackets.service.projection` (proyección de la previa y `/seeding/<slug>/bracket`); este último también toma de la copia el ID del evento.

## Bajas, cambios y reasignaciones

- Baja de inscripción: `active = false`, `removed_at`; la previa deja de mostrarla. Si vuelve a inscribirse con el mismo entrant, se reactiva y se limpia `removed_at`.
- Cambio de tag, prefijo o país: se actualiza la fila del participante; la identidad sigue siendo el Player.id.
- Pareja de dobles que cambia: el roster de esa inscripción pasa a ser exactamente el que start.gg lista.
- Cambio de seeding o reasignación de pool: la misma fila del seed cambia `seed_num`, `group_seed_num` o `phase_group_id`. Seed que start.gg deja de listar (baja): `active = false`.
- Pools rehechos (IDs nuevos): los anteriores quedan `active = false` y los seeds apuntan a los nuevos.
- Bracket que empieza o se rehace: los sets de vista previa cambian de ID; los que start.gg ya no lista quedan `active = false`. Un resultado cargado actualiza estado, ganador y marcador del mismo set.
- Torneo que sale del calendario de start.gg: `in_calendar = false`; sus datos se conservan.
