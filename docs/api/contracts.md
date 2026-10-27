# Contratos iniciales

Base: `/api/v1`. JSON UTF-8. Versión de aplicación `0.1.0`. Sin autenticación en estas rutas públicas de lectura. Las únicas escrituras son las de seeding (Misión 05), protegidas con clave de administración.

| Método y ruta | Éxito | Error previsto |
| --- | --- | --- |
| GET /health/live | 200 `{"status":"alive"}` | Independiente de PostgreSQL |
| GET /health/ready | 200 `{"status":"ready"}` | 503 `{"status":"unavailable"}` |
| GET /meta | 200, estructura debajo | 500 genérico ante fallo inesperado |

```json
{"name":"Smash PY Hub","version":"0.1.0","api_version":"v1","capabilities":["health","metadata","tournaments","events","players","results","statistics","head-to-head"]}
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

## Estadísticas Misión 03

| GET bajo `/api/v1/players/{id}` | Respuesta |
| --- | --- |
| `/statistics` | StatisticsView: jugador, filtros y agregados competitivos |
| `/matches` | MatchPage: historial descendente de sets elegibles |
| `/opponents` | OpponentPage: rivales por cantidad descendente y UUID ascendente |
| `/placements` | PlacementPage: placements finales confirmados por evento |
| `/head-to-head/{opponent_id}` | HeadToHeadView: identidades, totales simétricos e history ascendente paginado |

Todos requieren `game_id: UUID`; opcionales `mode=singles|doubles` (default singles), `tournament_id`, `community_id`, `date_from`, `date_to`. El juego es obligatorio para impedir agregados multijuego. Los listados y H2H aceptan page>=1 y page_size 1..100 (default 20); statistics no acepta parámetros de paginación. País/región pendientes: se rechazan, al igual que cualquier parámetro no admitido. Los timestamps requieren offset, usan `[desde,hasta)` y desde<hasta. Sets se filtran por completed_at; inscripciones/placements por inicio de torneo porque no tienen otra fecha propia. Fechas desconocidas se excluyen de ventanas fechadas y quedan null en consultas históricas sin fecha.

`filters` aparece en todas las respuestas; las páginas contienen items,total,page,page_size,filters. El total se calcula antes de paginar; history H2H tiene esa misma forma y sus totales globales no dependen de la página. Todos los órdenes se desempatan con UUID; fechas null al final. Sin sets: W/L y cantidades son 0, porcentajes/fechas/último torneo/mejor placement ausentes son null. A/B y B/A conservan sets, invirtiendo W/L y scores. Comparación consigo mismo: 422. Jugador inexistente o sin participación publicada: 404; juego/torneo/comunidad sin coincidencias: 200 vacío. Filtros inválidos/desconocidos: 422. No se exponen resultados administrativos en estas rutas.

`PlayerDetail` añade `scopes: [{game_id,game_name,mode}]`, con ámbitos confirmados de inscripciones públicas, sin afirmar sets jugados. Un registro sin puntuaciones puede ser elegible exclusivamente para W/L bajo la excepción de evidencia del clasificador compartido; su motivo se devuelve explícitamente sin cambiar flags persistidos de auditoría. Ver [reglas, fórmulas y dobles](../statistics.md) y ADR-010. El snapshot OpenAPI incluye modelos tipados y validación; la suite comprueba igualdad con la factory.

## Seeding (Misión 05)

| Método y ruta bajo /api/v1 | Acceso | Respuesta |
| --- | --- | --- |
| GET /seeding?kind=seeding\|ranking | público | `[{slug, name, kind, country_code, event_date, window_start}]` |
| GET /seeding/{slug} | público | Evento, período, corte de datos, estado de la descarga, conteos del dataset, fusiones, último cálculo y `seeds` (seed final, seed del método, métricas, `reasons`, `flags`, `override`) |
| GET /seeding/{slug}/export.csv | público | CSV UTF-8 con BOM, en el orden final |
| GET /seeding/{slug}/session | admin | Valida la clave y devuelve el nombre registrado |
| GET /seeding/{slug}/audit | admin | Últimos 100 cambios |
| POST /seeding/{slug}/recalculate | admin | `{window_start?, window_end?, refresh?, parameters?, method?}`. `method` cambia solo el método oficial y conserva el resto de los parámetros. Sin `refresh`: 200 y nuevo cálculo con los datos cargados. Con `refresh`: 202 y descarga de start.gg en segundo plano |
| PUT /seeding/{slug}/overrides/{player_id} | admin | `{seed, reason}` fija el seed del jugador |
| DELETE /seeding/{slug}/overrides/{player_id} | admin | Quita el ajuste manual |

Clave: `Authorization: Bearer <ADMIN_TOKEN>`; `X-Admin-Name` es opcional y solo va al registro. Errores: 401 clave incorrecta, 429 demasiados fallos, 503 edición deshabilitada, 404 proyecto inexistente, 409 descarga en curso, 422 período o seed inválidos (`detail` en español). Las fechas llevan zona horaria y el final del período es exclusivo. `window_start` no puede ser anterior a los datos descargados salvo con `refresh`.

### Métodos y rankings (Misión 05.1, ADR-012)

`GET /seeding/{slug}` agrega `kind` (`seeding` o `ranking`), `country_code`, `method` (método oficial) y `methods` (`[{id, label, description}]`). Cada fila de `seeds` agrega `scores` y `ranks` por método, `reasons_by_method`, `elo`, `bradley_terry`, `points`, `win_rate`, `wilson` y `eligible` (en rankings, si llega al mínimo de sets). Métodos: `combined`, `glicko2`, `elo`, `bradley_terry`, `points`, `wilson`. En rankings `PUT /overrides` responde 422.

### Administración desde la web (Misión 05.2)

| Método y ruta bajo /api/v1 | Acceso | Respuesta |
| --- | --- | --- |
| GET /seeding/session | admin | Valida la clave sin elegir proyecto |
| POST /seeding | admin | `{kind, name, slug?, event_url? (seeding), country? (ranking), window_start, end, download=true}` → 201 `{slug, kind, downloading}`. 409 si el slug existe; 422 si el link no es de start.gg o el evento no existe |
| PUT /seeding/{slug}/merges | admin | `{from_player_id, to_player_id}`; el destino tiene que estar en la lista. En un seeding, dos inscritos se marcan como duplicados, no se fusionan |
| DELETE /seeding/{slug}/merges/{player_id} | admin | Deshace la fusión |
| PUT /seeding/{slug}/duplicates | admin | `{player_id, keep_player_id}`, solo seeding |
| DELETE /seeding/{slug}/duplicates/{player_id} | admin | Deshace la marca |

Cada cambio de identidad recalcula al instante si el proyecto ya tiene datos. `GET /seeding/{slug}` agrega `merge_candidates`: IDs con el mismo tag normalizado que un jugador de la lista, con sus sets. Son sugerencias, no fusiones.

## Jugadores con mains e importación web (Misión 06, ADR-013)

`GET /players` y `GET /players/{id}` agregan `mains`: `[{character, games, share}]`, los personajes más usados en partidas de singles de sets elegibles (2 en el listado, 5 en la ficha). Puede venir vacío si los torneos no informaron personajes.

| Método y ruta bajo /api/v1 | Acceso | Respuesta |
| --- | --- | --- |
| POST /imports/startgg | admin | `{source: "country", country, window_start, end}` o `{source: "links", urls: [...]}` → 202. 409 si ya hay una importación en curso; 422 sin token de start.gg o con links que no son de start.gg |
| GET /imports/status | admin | `{status, total, done, current, results: [{slug, name, status, error?, counts?, conflicts?}]}` |

## Marca de ranking e íconos (Misión 07)

`TournamentView` agrega `counts_for_ranking` (por defecto `true`). `PUT /tournaments/{id}/ranking` (admin) recibe `{counts}` y recalcula al instante los rankings que ya tienen datos. Los sets de eventos de torneos desmarcados no cuentan en ningún ranking; `GET /seeding/{slug}` de un ranking lista sus nombres en `excluded_tournaments`. Los mains (`MainView`) agregan `icon`, el ícono de stock de start.gg (solo URLs de `images.start.gg`), y las filas de seeding y ranking incluyen `mains` del jugador según los torneos importados al hub.

### Vista pública y borradores (Misión 08)

`GET /seeding` y `GET /seeding/{slug}` aceptan la clave de forma opcional. Sin clave: solo publicados y una vista reducida (`public: true`, `method_label`, `seeds: [{seed, gamer_tag, mains, ...}]`). Con clave: la vista completa (`public: false`, `published`). `PUT /seeding/{slug}/publish` (admin) recibe `{published}`. `export.csv` pasa a requerir la clave.
