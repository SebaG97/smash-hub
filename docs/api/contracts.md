# Contratos iniciales

Base: `/api/v1`. JSON UTF-8. Versión de aplicación `0.1.0`. Sin autenticación en estas rutas públicas de lectura; no existe ninguna escritura pública.

| Método y ruta | Éxito | Error previsto |
| --- | --- | --- |
| GET /health/live | 200 `{"status":"alive"}` | Independiente de PostgreSQL |
| GET /health/ready | 200 `{"status":"ready"}` | 503 `{"status":"unavailable"}` |
| GET /meta | 200, estructura debajo | 500 genérico ante fallo inesperado |

```json
{"name":"Smash PY Hub","version":"0.1.0","api_version":"v1","capabilities":["health","metadata","tournaments","events","players","results"]}
```

Readiness ejecuta `SELECT 1` con timeout de conexión de 3 segundos y statement timeout de 5 segundos. Confirma conectividad, no estado de migración ni disponibilidad de proveedores. Consultar Alembic para comprobar revisión instalada. Liveness no usa ningún servicio externo.

OpenAPI se genera en `/api/openapi.json`; Swagger UI en `/api/docs` y ReDoc en `/api/redoc`. Los esquemas de respuesta están declarados con Pydantic. [Snapshot del contrato](openapi.json) generado desde la factory y verificado por tests.

Fallos inesperados devuelven `{"detail":"Internal server error"}` sin traceback. CORS acepta únicamente los orígenes explícitos configurados y GET. La API pública no acepta tokens de start.gg; solo la CLI utiliza el secreto de entorno.

Los contratos internos `ExternalReference` y `CompetitionProvider` reservan referencia de proveedor, fecha de sincronización y consulta de torneos. `RankingScope` y `RankingCalculator` reservan el ámbito competitivo sin implementar Glicko-2. No son endpoints disponibles.

## Consultas competitivas Misión 02

| Ruta GET bajo /api/v1 | Respuesta |
| --- | --- |
| /tournaments | Page[TournamentView] |
| /tournaments/{id} | TournamentView |
| /tournaments/{id}/events | Page[EventView] |
| /events/{id} | EventView |
| /events/{id}/entrants | Page[EntrantView] con integrantes individuales |
| /events/{id}/sets | Page[SetView] con lados, score nullable y ganador |
| /players | Page[PlayerView] |
| /players/{id} | PlayerDetail con aliases y history paginado |

Page = `{items, total, page, page_size}`. page >= 1; page_size predeterminado 20, máximo 100. Parámetros inválidos: 422. UUID válido inexistente o entidad de torneo no publicado: 404. Colección vacía o página fuera de rango: 200 con items vacío. No existe POST de importación: 405 en rutas de lectura.

Filtros: tournaments admite q por nombre, status y game_id; events por torneo admite game_id; entrants admite q por nombre; sets admite status; players admite q por tag actual o alias. q máximo 120 caracteres, coincidencia literal sin semántica de comodines SQL. Orden estable con UUID de desempate: torneos por inicio descendente (null al final); eventos por nombre; entrants por placement, seed (null al final); sets por finalización descendente; jugadores por tag. Historial de jugador por fecha de torneo descendente y evento/entrant; page/page_size controlan history.

TournamentView distingue participant_count (personas del torneo) de entrant_count (suma de inscripciones a eventos); una persona puede contar en varias inscripciones. games enumera juegos de sus eventos, source el proveedor y synced_at la última sincronización completa. EventView cuenta entrants persistidos y expone tamaño de equipo estructurado. Placement solo se publica como final cuando la fuente lo marca isFinal. Scores y fechas ausentes permanecen null; estado observado y resolución se muestran por separado (ver Misión 02.1), sin convertirlos en victorias jugadas.

Las colecciones se consultan mediante SELECT paginados y agregados de lote, evitando consultas por cada fila en endpoints públicos. No se devuelven IDs globales de proveedor, job IDs, conflictos, payloads, tokens, localización de jugadores ni contactos. Las entidades se filtran por tournament.published; una reimportación fallida mantiene la versión anterior confirmada.

Regenerar OpenAPI y diccionario con `python scripts/generate_schema_docs.py` desde raíz, en un entorno con dependencias de API. El snapshot se verifica con test_openapi_snapshot.

## Misión 02.1 — Semántica de sets

`GET /events/{id}/sets` separa estado y resolución. `status` ahora es lifecycle_status: pending, in_progress, completed, not_played o unknown. `resolution`: unresolved, played, dq, bye, placeholder o conditional_unused. Se agregan classification_reason (evidencia de clasificación), source_state entero nullable, round_number, stats_eligible y ranking_eligible. El JSON original y los IDs externos permanecen administrativos.

Filtros tipados: status, resolution y view=matches|bracket|all. Default matches excluye placeholder y conditional_unused; bracket contiene esas entradas y all conserva acceso al conjunto completo. Filtros se intersectan: para pedir placeholders explícitamente usar view=bracket o all. Un parámetro no admitido devuelve 422. La paginación y orden estable se aplican después de filtrar.

completed no significa victoria/derrota jugada: BYE y DQ tienen lifecycle completed pero su resolución propia y ambas elegibilidades false. Un final sin scores suficientes tiene status=completed, resolution=unresolved y no es elegible. El campo status interno legado de PostgreSQL no se publica. Este cambio de semántica del contrato inicial de Misión 02 se coordina con la web en la misma entrega; no hay clientes publicados ni despliegue automático.

La vista de evento separa «Sets y resultados» de «Posiciones del bracket y rondas no disputadas». BYE se muestra como pase libre sin partido jugado; DQ como descalificación excluida de victorias/derrotas jugadas; el avance por BYE/DQ no se etiqueta como victoria jugada. Un placeholder/reset no utilizado no muestra un oponente ficticio ni la etiqueta Pendiente.
