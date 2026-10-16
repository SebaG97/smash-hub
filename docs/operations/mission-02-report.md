# Informe de entrega — Misión 02

> Consolidación autorizada (16/10/2026): se revisaron los cambios de ambas misiones, la cadena 0001 → 0002 → 0003 y los archivos nuevos. Validación repetida: 108 tests backend con PostgreSQL efímero aislado, 12 frontend, Ruff, ESLint, Prettier, build y TypeScript aprobados. Búsqueda de secretos sin incidencias; .env y temporales excluidos. Se prepara el commit `feat: implement startgg import and set classification` en `feature/mission-02-startgg-import`, seguido de la rama autorizada `feature/mission-03-player-statistics`. Los estados «sin commit» y «no iniciar Misión 03» del informe original describen el momento de su entrega; esta autorización posterior habilita la continuación. Sin push, producción ni despliegue.

> Actualización Misión 02.1: este documento conserva los conteos de la validación anterior a 0003. La auditoría posterior identifica los 103 «pendientes» como placeholders y recupera dos resets INVALID antes omitidos; los resultados jugados no cambian. Consultar el [informe Misión 02.1](mission-02-1-report.md) para la clasificación vigente, matrices y pruebas.


Fecha: 16 de octubre de 2026. Rama: `feature/mission-02-startgg-import`. Implementación y validación automatizada preparadas para revisión. **Importación real, reconciliación y reimportación de los tres torneos de singles verificadas. Revisión del responsable pendiente; inspección visual interactiva no disponible.** No se hizo commit, push, despliegue, modificación de producción ni creación de recursos DigitalOcean. No se inició Misión 03.

## Resultado técnico

Se conservan Next.js + FastAPI + PostgreSQL + Alembic y las 19 tablas de Misión 01. Se añade cliente start.gg HTTPX asíncrono con documentos GraphQL separados, parser de URL seguro, timeout, paginación completa, reintentos y backoff/jitter. STARTGG_API_TOKEN es opcional en startup y obligatorio únicamente para llamadas reales del importador. No hay endpoint público de importación.

El servicio usa identidades globales Player.id, participantes con ámbito de torneo, aliases observados, entrants y sus miembros. No fusiona por gamerTag. Conserva resultados originales y cambios posteriores, protege correcciones con locks manuales y registra conflictos en import_jobs. La descarga completa se valida antes de una transacción de publicación. Una falla revierte dominio y conserva el job fallido; reintentar es seguro.

## Migración y esquema

Nueva revisión incremental: `apps/api/migrations/versions/0002_startgg.py`, down_revision 0001. La revisión inicial permanece sin cambios. No hay nuevas tablas.

| Tabla modificada | Campos/comportamiento |
| --- | --- |
| tournaments | published, status, location JSON, synced_at |
| events | status, competition_type, num_entrants |
| tournament_participants | external_id scoped único y manual_locked |
| event_entrants | placement nullable |
| players | manual_locked para tag actual |
| sets | manual_locked, ranking_eligible, source_result, result_history; estado incomplete; fecha final nullable |
| external_mappings | manual_locked |
| import_jobs | counts y conflicts JSON; una fila por intento con clave slug:UUID |

Se mantienen FKs y triggers competitivos. completed requiere scores/ganador válidos; una fecha ausente no se inventa. ranking_eligible exige completed con fecha y solo prepara una candidatura futura; no hay cálculos de ranking. Downgrade a 0001 se rechaza si implica perder resultados incompletos o fechas finales ausentes; el test comprueba rollback de esa migración rechazada. También se verifica conservación de filas compatibles al revertir/reaplicar.

## Documentos GraphQL

En `apps/api/app/integrations/startgg/graphql/`: tournament, event, participants, entrants, standings y sets. Revisión de campos/tipos/argumentos contra documentación oficial, incluyendo referencia oficial que redirige al esquema publicado. Queries ejecutadas con MockTransport en tests completos de cliente/CLI. No se realizó introspección completa del esquema; los seis documentos sí se ejecutaron autenticados contra los tres torneos reales, sin errores GraphQL.

## API y frontend

Ocho endpoints GET bajo `/api/v1`: tournaments; tournaments/{id}; tournaments/{id}/events; events/{id}; events/{id}/entrants; events/{id}/sets; players; players/{id}. Incluyen Pydantic, paginación, filtros, orden estable, 404 y consultas públicas en lote. No exponen IDs de proveedor, jobs, payloads, conflictos ni secretos. Solo publican datos de torneos confirmados.

Vistas: `/tournaments`, `/tournaments/[id]`, `/events/[id]`, `/players`, `/players/[id]`; aliases de navegación `/torneos` y `/jugadores` redirigen. Se conserva identidad visual y se añaden tarjetas responsive, carga, errores/reintento, vacío, búsqueda, paginación, miembros individuales, placements, sets y tags históricos. Rankings y estadísticas permanecen pendientes; no se inventan cifras competitivas. La web consume exclusivamente FastAPI.

## Validación ejecutada

| Control | Resultado |
| --- | --- |
| Pytest con PostgreSQL 17.7 efímero aislado | **83 passed**, sin omisiones |
| Ruff lint y formato backend | Aprobados |
| Vitest frontend | **11 passed**, dos archivos |
| ESLint y Prettier | Aprobados |
| Next.js build y TypeScript | Aprobados |
| Snapshot OpenAPI frente a factory | Aprobado en suite |
| Migraciones, metadata, rollback y reaplicación | Aprobados en PostgreSQL aislado |
| doctl schema-only del App Spec y spec compuesto existentes | Ambos exit 0; sin acceso a cuenta/despliegue |
| Git diff --check y búsqueda de patrones comunes de secretos en entrega | Sin incidencias detectadas |

La ejecución final de Compose y los controles de imagen se registran localmente en `.cache/mission-02-final-real-tests.log`; ese log no se versiona. CI conserva sus comandos y servicios; **la ejecución remota de GitHub Actions no se realizó**, ya que no se publicó esta rama. Los controles equivalentes se ejecutaron localmente. Persisten avisos de deprecación conocidos de Starlette/AnyIO y configuración Vitest; no son fallos. No se realizó inspección visual interactiva de navegador: no había navegador conectado; HTTP y componentes sí se verificaron.

La suite cubre singles y dobles; persona en varios eventos; tags cambiantes; homónimos; identidad global ausente; completed/pending/DQ/BYE; puntuación/fecha ausentes; casos ambiguos; torneo vacío; paginación múltiple/incompleta; errores HTTP/GraphQL/parciales/redirects; rate limit y espaciado; repetición sin duplicados; falla a mitad; conflictos; correcciones; bloqueos manuales; URLs maliciosas. Una prueba específica importa tres torneos **sintéticos** fuera de orden y verifica identidad compartida, aliases y reimportación sin duplicados.

## Validación real ejecutada — 16/10/2026

Token verificado mediante el preview CLI de gg-fest-x-eon. Se comprobó ENVIRONMENT=development y destinos de aplicación/migración en postgres:5432/smashhub antes de operar. Migración 0002 y bootstrap aplicados exclusivamente a PostgreSQL local. Los tres torneos se importaron y se reimportaron con la CLI realmente implementada, sin mutaciones de start.gg.

| Torneo | Eventos | Participantes | Entrants | Jugados completed | Pendientes | DQ | BYE | Incompletos | Placements finales | Conflictos identidad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gg-fest-x-eon | 1 | 25 | 25 | 48 | 27 | 0 | 27 | 0 | 24 | 0 |
| game-over-sep | 1 | 21 | 21 | 40 | 34 | 0 | 28 | 0 | 21 | 0 |
| super-smash-burgame-7 | 1 | 17 | 17 | 28 | 42 | 5 | 28 | 0 | 17 | 0 |

Totales: 3 eventos singles, 63 participaciones, 63 entrants, 307 sets: 116 jugados, 103 pendientes, 5 DQ y 83 BYE. Los BYE no son sets jugados ni habilitan ranking. Los tres eventos publican type=1, teamRosterSize=null; se aplicó el campo estructurado, sin inferir modalidad por nombre. Ningún resultado final carecía de completedAt en estas respuestas.

Se descargó nuevamente la selección original de GraphQL y se compararon todos los participantes/tags históricos, vínculos de identidad, entrants, seeds, integrantes, placements finales, estados, rondas, fecha, ganador y scores por lado con PostgreSQL. También se verificó source_result frente al snapshot mínimo validado. Resultado: **cero diferencias**. No hubo errores GraphQL, campos obligatorios faltantes ni incompatibilidades del modelo con los tres torneos.

GG Fest X EON devuelve 25 standings, pero solo 24 con isFinal=true: el restante tiene placement=9 e isFinal=false. Se conserva su placement final como null; no se inventó ni promovió el provisional. Los eventos finalizados todavía contienen sets state=1 (27, 34 y 42 respectivamente): se mantienen pendientes sin convertirlos en resultados finales. Los 5 DQ de Burgame incluyen marcador -1 y etiqueta DQ; los BYE presentan evidencia explícita de fuente. La normalización conservadora quedó contrastada con estos casos reales, sin implicar compatibilidad universal con todos los videojuegos.

Identidades: 38 Player.id globales distintos y 38 jugadores internos; 63 inscripciones históricas y 39 aliases. 18 jugadores aparecen en al menos dos torneos y 7 en los tres. Coincidencias por pares: GG Fest/Game Over 13; GG Fest/Burgame 11; Game Over/Burgame 8. Cada referencia global se verificó contra la participación correspondiente y un único jugador interno; cero conflictos o fusiones por tag. No hubo participantes sin identidad global en estos tres casos.

Reimportación: cada torneo mantiene su UUID y devuelve created=0, updated=0, conflictos=[]; skipped=154, 146 y 139 respectivamente. Además de conteos, se compararon los conjuntos de UUID y hashes de estado lógico en las 18 tablas de dominio/referencia (excluidos import_jobs y timestamps operativos): **ninguna tabla cambió**. Quedaron seis jobs completed, uno por cada ejecución real persistente. La única actualización de jugador en la primera importación de Burgame corresponde a evidencia de tag posterior; no fue una corrección manual ni una modificación del proveedor.

Se verificaron 59 respuestas HTTP 200 de API sobre los datos reales: listados paginados, detalles de los 3 torneos y 3 eventos, entrants, sets, los 38 perfiles y búsqueda vacía, más una comprobación adicional de 404. Se comprobaron 11 rutas web HTTP 200, incluidos detalles y redirecciones /torneos y /jugadores. La inspección visual/hidratación en navegador interactivo no pudo realizarse: el inventario estaba vacío y Chrome y el navegador integrado no estaban disponibles. Las vistas sí se verificaron por HTTP, pruebas de componentes y compilación; no se presenta esto como revisión visual.

Problemas de entorno resueltos: la imagen API aún era de Misión 01 y faltaba HTTPX; se reconstruyó localmente. El proceso Next.js antiguo devolvía 404 para las nuevas rutas; reiniciarlo las registró correctamente. No se necesitaron cambios de queries, modelo, resultados ni código de dominio para importar estos datos.

Dobles continúa validado exclusivamente con fixtures sintéticos y pruebas automatizadas; su ausencia real en la comunidad durante 2026, confirmada por el responsable, no bloquea aprobación. No se inventaron torneos ni resultados de dobles. Ver [matriz actualizada](mission-02-validation-plan.md) y [evidencia agregada](mission-02-real-evidence.json).

## Ejemplo y reimportación

Desde apps/api con configuración privada y PostgreSQL local:

```sh
python -m app.cli.import_tournament --slug gg-fest-x-eon --dry-run
python -m app.cli.import_tournament --slug gg-fest-x-eon
# Repetir el segundo comando para verificar la sincronización.
```

Estos comandos se ejecutaron contra el torneo real autorizado, además de las importaciones y reimportaciones de game-over-sep y super-smash-burgame-7. Dry-run no abre PostgreSQL; valida descarga, estructura, referencias y rosters y muestra cantidades. No anticipa conflictos locales. Éxito devuelve JSON y exit 0; errores operativos exit 1; configuración/argumentos inválidos exit 2. La CLI bloquea ENVIRONMENT=production en esta misión.

Con el mismo snapshot, la repetición mantiene UUID y estado lógico, con created=updated=0. Crea un nuevo intento administrativo y actualiza timestamps de sincronización. No borra historia ausente. Un cambio aceptado de resultado conserva previous/replacement; revisiones más antiguas se omiten y correcciones bloqueadas generan conflicto con candidato propuesto. Una identidad contradictoria revierte la publicación, sin merge arbitrario.

## Límites y revisión pendiente

Importaciones persistentes se serializan por proveedor en la base; previews y otros consumidores del mismo token deben operarse sin concurrencia para mantener el límite agregado. Se mantiene una conexión CLI y la descarga en memoria; no hay reanudación por página. Un cierre abrupto puede dejar un intento running histórico aunque PostgreSQL libere locks y revierta cambios; una nueva ejecución crea otro intento seguro.

El proveedor no garantiza snapshot entre páginas. Se rechazan totales cambiantes, referencias rotas y respuestas parciales, pero cambios que mantengan totales pueden requerir otra sincronización. Equipos de roster variable y sets con más de dos lados requieren extensión explícita; DQ/BYE ambiguos se conservan incompletos. La normalización conservadora de DQ/BYE se contrastó con los datos reales autorizados; otros formatos requieren validación propia. La política de corrección manual requiere activar el lock junto con la corrección; no se ofrece UI de administración.

App Specs no se modificaron. El fragmento de migración DigitalOcean sigue aprobado únicamente para 0001; no es una autorización de despliegue de 0002. No se conectó a PostgreSQL Managed. Los fixtures solo se usaron en la base efímera; los tres torneos reales permanecen en PostgreSQL local de desarrollo para revisión.

## Documentación y Git

Actualizados README, arquitectura general/módulos, modelo y diccionario, contratos y snapshot OpenAPI, seguridad, desarrollo local, migraciones y DigitalOcean. Creados integración startgg, runbook tournament-import, este informe, plan de validación y ADR-006/007/008 (identidades, correcciones y transacciones/idempotencia).

Rama de trabajo: `feature/mission-02-startgg-import`. Cambios locales sin commit ni push, listos para revisar. La migración 0001, specs DigitalOcean y workflows existentes permanecen intactos. No hay token real en los archivos de entrega.

Pendientes de revisión: inspección visual interactiva móvil/escritorio y aprobación del responsable. La validación real de los tres torneos de singles ya se ejecutó y documentó. Una futura Misión 03 requerirá alcance y aprobación propios; posibles temas son autorización administrativa y operación de jobs, sin implementarlos aquí. Esperar revisión y aprobación del responsable.
