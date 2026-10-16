# Estadísticas competitivas y Head-to-Head

Las métricas se calculan en FastAPI desde PostgreSQL publicado. No existen ratings, rankings, seeding, personajes inferidos ni tablas precalculadas. El frontend presenta las respuestas de nuestra API.

## Ámbito y filtros

Todos los endpoints requieren `game_id` UUID interno. `mode=singles` es el valor predeterminado; `doubles` es independiente. Un evento debe tener `team_size` y `competition_type` coincidentes, respectivamente 1/1 o 2/2. Una clasificación desconocida o contradictoria se excluye. `PlayerDetail.scopes` enumera los juegos y modalidades de inscripciones publicadas y confirmadas, sin depender de la página de historial ni afirmar actividad competitiva.

Opcionales: `tournament_id`, `community_id`, `date_from`, `date_to`. Se intersectan antes de agregar/paginar. IDs existentes sin resultados coincidentes producen resultados vacíos; jugadores inexistentes o sin participación pública producen 404. UUID/parámetros inválidos y compararse consigo mismo producen 422. Los parámetros no admitidos se rechazan: país y región siguen pendientes porque no hay datos consistentes de residencia o localización de torneos que permitan una política fiable. La comunidad corresponde al organizador del torneo, nunca a una afiliación inferida del jugador.

Fechas ISO 8601 con offset obligatorio. Intervalo semiabierto `[date_from, date_to)`; inicio estrictamente anterior al final. Para sets se usa exclusivamente `sets.completed_at`, nunca fecha de importación o inicio de torneo como sustituto. Sin filtros temporales se incluyen sets válidos sin fecha, con `null`, ordenados al final; con límites temporales se excluyen porque su pertenencia al intervalo no puede determinarse. Mínimo/máximo y último torneo se obtienen únicamente de sets con fecha conocida. Si todos carecen de fecha, esos campos son `null` aunque haya sets. El UUID desempata todos los órdenes.

Inscripciones y placements no tienen timestamp propio: el mismo intervalo se aplica explícitamente a `tournaments.starts_at`. Un torneo sin inicio conocido no pertenece a un período fechado. Por esta diferencia un set dentro del período puede pertenecer a un torneo cuya inscripción/placement queda fuera. No se infieren inscripciones o placements a partir de sets ni viceversa. La interfaz indica que los filtros ingresados usan la zona local del navegador y los convierte a instantes ISO; las fechas de resultados se muestran en America/Asuncion.

## Elegibilidad

La política central `statistics.policy` consume `stats_eligible`, `lifecycle_status` y `resolution` de Misión 02.1. El camino normal exige final `played`; jamás basta `status=completed`. BYE, DQ, placeholder, reset condicional no usado, pendientes, ganador ausente o ambigüedad no aportan W/L. El reset efectivamente jugado sí puede aportar un resultado.

La consulta verifica además dos lados, exactamente un ganador, rosters completos y distintos, sin jugadores compartidos por ambos lados. Las claves y la consulta producen una sola fila por UUID de set. Alias y tags no intervienen en claves, joins ni agrupaciones. Se excluyen conservadoramente sets con `manual_locked=true` en el set o su mapping start.gg: el modelo no distingue una corrección pendiente de otra ya aprobada. Una revisión administrativa debe resolver la situación y desbloquear explícitamente para volver a incluirla; no se ignoran locks.

Excepción pedida en Misión 03: final con dos oponentes, ganador explícito y ambas puntuaciones ausentes. La evidencia se valida mediante `scoreless_statistics_evidence`, dentro del clasificador compartido de start.gg. Requiere state=3, dos entrants distintos, winnerId de uno de ellos, ausencia de placeholder y de etiquetas DQ/BYE, ambas puntuaciones nulas y clasificación previa `completed/unresolved`. Solo se evalúan registros normalizados versión >=2 con `incomplete` y `final_result_insufficient`. Scores parciales, negativos o contradictorios no habilitan la excepción. Los lados internos también deben conservar un ganador válido.

Esta excepción de lectura produce `stats_eligible=true` en el historial competitivo y `eligibility_reason=final_two_opponents_winner_without_scores`; **no modifica** el resultado, la clasificación importada ni los flags persistidos de Misión 02.1. Por ello un registro excepcional puede conservar `stats_eligible=false` en el endpoint de auditoría del evento. ADR-010 documenta la diferencia y las pruebas la delimitan. No se inventa score, fecha ni resultado por juego individual.

## Métricas

| Campo | Definición |
| --- | --- |
| sets_played | Sets elegibles únicos del jugador en el ámbito |
| wins / losses | Un resultado por set: ganador / perdedor |
| win_rate | `wins / (wins + losses) * 100`, redondeado a dos decimales; `null` sin denominador |
| tournaments_played | Torneos distintos con al menos un set elegible |
| tournaments_registered | Torneos distintos con inscripción del jugador a un evento del ámbito, con o sin sets |
| first_set_at / last_set_at | Fechas extremas conocidas de sets elegibles |
| latest_tournament | Torneo del último set fechado; UUID desempata |
| best_final_placement | Menor placement positivo final confirmado; `null` si no hay ninguno; no es ranking de habilidad |
| unique_opponents | Jugadores internos distintos en lados opuestos de sets elegibles |

`event_entrants.placement` contiene exclusivamente standings que el importador verificó con `isFinal=true`. Provisionales y ausentes son `null`; el endpoint placements los omite, sin convertirlos en cero. El listado de placements conserva una entrada por evento, incluida la distinción entre eventos del mismo torneo.

Dobles atribuye el resultado del equipo a cada miembro **solo dentro de mode=doubles**. El historial contiene un set y el roster contrario completo; los rivales frecuentes son miembros de equipos contrarios y un compañero nunca es rival por compartir lado. En dobles la suma de sets por rival puede superar los sets del jugador porque cada set tiene dos oponentes individuales; nunca se presenta como rendimiento individual de singles ni ranking.

## Head-to-Head e historiales

`head-to-head/{opponent_id}` usa UUID internos y filtra los mismos sets desde la perspectiva de A. Invertir A/B conserva encuentros, IDs, orden y fechas, e invierte victorias, derrotas y scores. En dobles cuenta únicamente cuando A y B pertenecen a equipos opuestos. Sin encuentros devuelve cero y porcentajes `null`, con ambas identidades actuales.

El historial H2H es ascendente; `/matches` es descendente; ambos ponen fechas desconocidas al final y desempatan por UUID. H2H incluye totales de **todo el filtro**, mientras `history` es una página. Un historial contiene torneo, evento, ronda, fecha nullable, roster rival, W/L, score nullable, entrant ganador, elegibilidad y fuente. Fuente start.gg se muestra solo con mapping del proveedor y la URL usa el slug validado del torneo; no se fabrica una ruta de evento a partir del slug interno `startgg-ID`. No hay consulta de resultados administrativos desde estas rutas: se auditan en el endpoint de sets existente.

Rivales: cantidad descendente y UUID de rival ascendente. Las cinco rutas usan las mismas reglas. Los listados aceptan `page>=1`, `page_size` entre 1 y 100, predeterminado 20; fuera de rango devuelven página vacía con el total real. Los endpoints no devuelven payloads, IDs externos, contacto ni localización del jugador.

## Consultas y operación

`repository` delimita eventos, rosters y universo SQL; `policy` aplica elegibilidad; `service` coordina agregaciones y presentación; `contracts` define respuestas; `router` valida HTTP. Una transacción REPEATABLE READ mantiene coherencia entre totales e historial de cada respuesta ante importaciones concurrentes. La excepción sin score lee únicamente candidatos incompletos del ámbito y verifica evidencia compartida; la vía normal agrega en SQL, sin cargar todos los sets en Python. Rivales se agrupan en SQL; tags de la página se cargan en lote, sin N+1.

Se reutilizan índices existentes de evento/juego/torneo, miembros/participante, lados/set/entrant y unicidad de mappings. El informe guarda EXPLAIN ANALYZE BUFFERS de universo, últimos resultados y rivales sobre los datos locales. El volumen observado no justifica migración 0004. No se incorporan servicios ni cachés. El universo SQL es reutilizable por futuros consumidores; no contiene cálculo de rating.

Validación reproducible, solo sobre la base local de desarrollo:

```powershell
docker compose run --rm --no-deps -T api python -m app.cli.validate_statistics --slugs gg-fest-x-eon game-over-sep super-smash-burgame-7
./scripts/dev.ps1 test
```

La CLI exige environment=development, host local/Compose y base smashhub; abre una transacción READ ONLY, no llama start.gg ni migra. Sus aserciones reconcilian cada jugador por torneo, sets únicos, W=L y simetría H2H. Pruebas automatizadas: exclusivamente PostgreSQL efímero de compose.test y fixtures sintéticos, sin proveedor externo. No ejecutar la suite destructiva contra desarrollo ni producción.
