# Diseño del sistema de logros (SH-ACH-01A)

Estado: **implementado** (SH-ACH-01, [ADR-023](../adr/ADR-023.md)), pendiente de publicación. Catálogo: [catalogo.md](catalogo.md). Decisiones: [README.md](README.md). Publicación: [operations/sh-ach-01.md](../operations/sh-ach-01.md).

> **Diferencias entre la implementación y esta propuesta**
> - **Humor:** público por defecto; el dueño oculta cada logro con `hidden` (en `player_achievements` y `prode_achievements`), sin la tabla `player_achievement_preferences`. Reemplaza §3.4.
> - **Una fila por jugador y logro** (`occurrence = ''`): se guarda el primer desbloqueo; la clave queda lista para logros repetibles.
> - **Vitrina:** `user_showcase` guarda `achievement_id` y `source` (`player` o `prode`), no la fila exacta.
> - **Prode:** se agregaron `status`, `revoked_at`, `event_at`, `evidence` y `hidden`; no `source` ni `rule_version`. `created_at` es el primer reconocimiento.
> - **Personas de referencia:** `achievement_subjects` con `active` además de `consent_at`. Sin las dos cosas, la colección no se evalúa ni se puede otorgar a mano.
> - **Evaluación automática:** apagada por defecto (`ACHIEVEMENTS_AUTO=false`). Recálculo manual desde `/admin`. Las marcas de cambio llegan en el mismo proceso, y hay una corrida periódica (6 h por defecto).

## 1. Revisión técnica del código actual

### 1.1 Qué datos hay

| Dato | Dónde | Calidad para logros |
| --- | --- | --- |
| Sets jugados con ganador, puntaje, ronda, `best_of`, `completed_at` | `sets`, `set_sides` | ✔ Solo cuentan los elegibles (`stats_eligible`): ya excluyen DQ, byes y placeholders. |
| Seeds y posiciones finales por evento | `event_entrants.seed`, `.placement` | ✔ Con la marca `tournaments.seeding_reliable` para descartar seedings poco fiables. |
| Evento principal o secundario | `events.main` + `competitions.roles.guess` | ✔ |
| Personajes por partida, con ganador de la partida | `set_selections` | ◐ Solo cuando se reportaron en start.gg. No hay colores. |
| Color preferido por personaje | `players.costumes` | Solo para imágenes; **no** dice qué color se usó en cada partida. |
| Ciudad del torneo | `tournaments.location.city` | ◐ Puede faltar. |
| Equipos | prefijos aprobados (`team_prefixes`) y `tournament_participants.prefix` | ◐ Desde la misión 15. |
| Rankings publicados por período | `ranking_snapshots` (+ `rating_snapshots`) | ◐ Solo las publicaciones guardadas. |
| Pools, fases y seeds por pool | `startgg_phases`, `startgg_phase_groups`, `startgg_seeds`, `startgg_sets` | ◐ Solo torneos seguidos por la sincronización (SH-SYNC-01, desde noviembre de 2026). Los torneos importados antes no tienen el pool de cada set. |
| Prode: pronósticos con historial y hora, candidatos con ID de start.gg y seed, puntajes, apertura y cierre | `prode_*` | ✔ |
| Cuentas y vínculo verificado cuenta ↔ jugador | `users`, `player_links` | ✔ |
| Identidad estable del jugador | `external_identities` (ID de jugador de start.gg → `players.id`) | ✔ |

### 1.2 Qué datos faltan

| Falta | Bloquea | Cómo se obtendría |
| --- | --- | --- |
| Serie de torneos (ediciones de un mismo circuito) | `bicampeon` | Campo `series` en `tournaments`, asignado por administradores. |
| Pool de cada set en torneos ya importados | `dueno_del_pool`, `esta_vez_si`, `no_pasar_pools`, `el_seeding_nos_odia` | Contarlos solo desde que existe la copia de pools, con «datos desde» visible. |
| Organizador del torneo | `fiel_al_regimen` | Guardar el dueño o los administradores del torneo de start.gg en la sincronización. |
| Color usado en cada partida | `vbash_rojo` | start.gg no lo informa. Sería manual o quedaría descartado. |
| Hora real de inscripción | `terere_rupa` | start.gg no la informa de forma fiable; la del hub es la de detección. |
| Temporadas del Prode | `season_champion` | Definir temporada (año calendario) y tabla anual. |

### 1.3 Lo que no se hace

- **Ninguna consulta a start.gg por visita.** Los logros se evalúan con los datos ya importados o sincronizados, y el Prode con los resultados guardados en `prode_questions.result`.
- **Ninguna evaluación al abrir un perfil.** Se evalúa en un trabajo de fondo (§8) y la web solo lee filas.

## 2. Rarezas y porcentajes

### 2.1 Rareza de diseño

La define el catálogo, y es la intención del diseñador: **común, raro, épico, legendario**. Es fija, se ve siempre (marco y color de la tarjeta) y no depende de los datos.

Compatibilidad: la columna `prode_achievements.rare` se conserva tal cual y no se usa para presentar. La rareza visible sale del catálogo por `kind`.

### 2.2 Rareza estadística

Para cada logro se calcula:

- `holders`: personas distintas que lo tienen activo.
- `universe`: personas elegibles (§2.3).
- `pct = holders / universe`.

La etiqueta estadística usa **otras palabras** para no confundirse con la de diseño:

| Porcentaje | Etiqueta |
| --- | --- |
| 0 personas | «Nadie todavía» |
| < 1 % | «Rarísimo» |
| 1–5 % | «Escaso» |
| 5–20 % | «Poco frecuente» |
| 20–50 % | «Frecuente» |
| > 50 % | «Muy frecuente» |

### 2.3 Universos elegibles

Cada logro declara su universo en el catálogo. Los universos por defecto son:

| Categoría | Universo |
| --- | --- |
| Competitivos, Trayectoria, Rivalidades, Secretos de bracket | Jugadores con ≥ 1 set elegible en un torneo publicado **dentro del período con datos** del logro. |
| Logros que exigen tamaño (p. ej. top 8 en ≥ 16) | Jugadores que jugaron al menos un evento que cumple ese tamaño. |
| Personajes y vBash con personajes | Jugadores con ≥ 1 partida con personaje reportado. |
| Pools | Jugadores con ≥ 1 evento con pools copiado. |
| Contra una persona de referencia (Spike, vBash) | Jugadores con ≥ 1 set oficial contra esa persona. |
| Prode | Usuarios con ≥ 1 Prode liquidado. |
| Comunidad (cuentas) | Cuentas activas. |
| Edición limitada | Quienes pudieron obtenerlo (p. ej. inscriptos de esa edición). |
| Manuales | Sin porcentaje: solo la cantidad de personas. |

### 2.4 Cuándo no se muestra el porcentaje

- **Muestra chica:** si `universe < 30`, se muestra la cantidad («3 jugadores») sin porcentaje, con la leyenda «muestra chica».
- **Historial incompleto:** si el logro depende de un dato parcial (◐), se muestra «datos desde {fecha}» y el universo se limita a ese período. Si la cobertura es < 50 % de los sets del período (p. ej. personajes reportados), se muestra la cantidad sin porcentaje.
- **Nadie lo consiguió:** «Nadie todavía», sin porcentaje ni «0 %».
- **Secretos:** el porcentaje se muestra aunque no se haya desbloqueado («??? — 2 % lo tiene»), sin nombre ni condición.
- **Estados dinámicos** (`lider`, `nuevo`, `especialista`, `camaleon`): «lo tienen ahora N»; no se los incluye en el progreso de colección.

### 2.5 Calibración antes de lanzar

Antes de publicar cada tanda se ejecuta el evaluador en modo «simulación», sin escribir, contra una copia de la base. Se compara la rareza de diseño con la estadística. Si un logro épico lo tiene más del 20 % del universo, o uno común menos del 1 %, se revisa el umbral antes de lanzarlo.

### 2.6 «Primero en conseguirlo»

Se muestra solo si:
1. el hecho tiene fecha real (`event_at`), y
2. la cobertura de datos del logro empieza **antes** del hecho más antiguo registrado (no hay huecos previos que pudieran esconder a otro).

Si no, se muestra «primer registro en Smash Hub». En empates del mismo día se muestran todos.

## 3. Secretos, ediciones limitadas, manuales y humor

### 3.1 Secretos
En el catálogo se ven como «???», con su categoría y rareza de diseño, y el porcentaje si aplica. Al desbloquearlo, la persona ve nombre, condición y contexto. En la ficha pública se ven solo si su dueño los destaca en la vitrina.

### 3.2 Ediciones limitadas
Llevan `available_from` y `available_to`. No cuentan para `coleccionista` ni para el progreso de categoría, y se muestran en una colección aparte («Ediciones»).

### 3.3 Manuales
Solo los otorgan administradores (`admin` o `superadmin`), con **motivo público obligatorio**, quedan en auditoría y se pueden revocar con motivo. No hay porcentaje. «Por Decreto Supremo» y «El Dictador ha Hablado» entran por este camino.

### 3.4 Humor (marca **h**)
Logros como `nerfeado_por_la_trama`, `los_johns`, `no_pasar_pools`, `jinx` y `nde_ru` se burlan con cariño, pero nadie los pidió.
- Se otorgan igual y su dueño los ve en su perfil.
- **Son públicos solo si el dueño lo elige** (casilla «mostrar en mi perfil»). Los jugadores sin cuenta vinculada no los muestran nunca.
- No aparecen en imágenes para compartir salvo que el dueño los destaque.

## 4. Persistencia y recálculo

### 4.1 Principios
- **Un solo catálogo** (`app/achievements/catalog.py`, en el código) y **dos almacenes según quién recibe el logro**: el Prode (cuentas) sigue en `prode_achievements`, y los de jugador van a una tabla nueva `player_achievements`. No es un sistema paralelo: comparten el catálogo, la API y los componentes, y el Prode conserva su tabla y sus `kind`.
- **Nunca se borra un logro para recrearlo.** El recálculo compara y aplica diferencias.
- Los estados dinámicos **no** se guardan: se calculan al vuelo como hoy.

### 4.2 Tabla nueva `player_achievements`

| Columna | Uso |
| --- | --- |
| `id` | UUID. |
| `player_id` | `players.id` (identidad estable, §6). |
| `achievement_id` | ID del catálogo (≤ 40). |
| `occurrence` | Qué lo hace único: `''` para logros de una sola vez, o el ID del evento o del rival en los repetibles. **Única por `(player_id, achievement_id, occurrence)`.** |
| `event_at` | Fecha real del hecho (`completed_at` del set o inicio del torneo), si se conoce. |
| `recognized_at` | Cuándo lo reconoció Smash Hub por primera vez. **Nunca se reescribe.** |
| `backfilled` | `true` si se otorgó en la carga retroactiva inicial. La interfaz dice «reconocido retroactivamente». |
| `tournament_id`, `event_id`, `set_id`, `opponent_player_id` | Origen y rival, cuando corresponda. |
| `evidence` | JSON con los valores que lo justifican (seeds, puntaje, conteos, versión de regla). |
| `source` | `auto` o `manual`. Con `manual`: `granted_by`, `reason`. |
| `rule_version` | Versión de la regla que lo otorgó. |
| `status` | `active` o `revoked`, con `revoked_at` y `revoked_reason`. |

### 4.3 Recálculo idempotente
1. El evaluador produce, para cada jugador, el conjunto esperado de `(achievement_id, occurrence, event_at, evidence, …)`.
2. Se compara con lo guardado:
   - nuevo → se inserta con `recognized_at = ahora`;
   - existe → se actualizan `evidence`/`event_at` si cambiaron, sin tocar `recognized_at`;
   - guardado pero ya no esperado (p. ej. se corrigió un set) → `status = revoked`, nunca se borra;
   - revocado que vuelve a cumplirse → se reactiva conservando su `recognized_at` original.
3. Los manuales no los toca el evaluador.
4. Toda la pasada corre en una transacción por lote y con bloqueo consultivo (como ya hacen la sincronización y los rankings), así que dos ejecuciones simultáneas no duplican nada.

**Fusión de jugadores duplicados:** al fusionar, los logros se mueven al jugador destino conservando `recognized_at`; si chocan, queda el más antiguo.

### 4.4 Prode: corregir el borrado y la recreación
Cambios aditivos en `prode_achievements`: `event_at`, `evidence`, `source`, `rule_version` y `status`/`revoked_at` (todas nulas o con valor por defecto).

- `settle` y `_lifetime` pasan de «borrar e insertar» al mismo diff de §4.3, con la clave única existente `(user_id, contest_id, kind)`. `created_at` se usa como `recognized_at` y deja de cambiar.
- Al **anular** un Prode liquidado, sus logros se marcan revocados en lugar de borrarse por cascada. El `ON DELETE CASCADE` se mantiene para el borrado físico, que no se usa.
- Recálculo histórico: `rebuild_achievements(contest)` vuelve a evaluar desde `prode_questions.result` y `prode_scores`, sin llamar a start.gg. Solo administradores, con entrada en `prode_audit_entries`.
- Logros que ya existen (hoy probablemente ninguno; ver el inventario): se conservan con su `created_at` y quedan con `rule_version = 1`.

### 4.5 Estadísticas materializadas
Tabla `achievement_stats(achievement_id, holders, universe, coverage_from, first_event_at, first_holders, computed_at)`. Se recalcula al terminar cada pasada del evaluador. La página de catálogo lee solo esta tabla.

## 5. Experiencia de usuario

### 5.1 Páginas
- **`/logros`, el catálogo completo.** Arriba, el progreso general y por categoría (barras). Filtros en chips desplazables: categoría, rareza de diseño, «obtenidos / no obtenidos / secretos», colección. Cada tarjeta muestra ícono, nombre, rareza (marco), etiqueta estadística, «N jugadores» y un tilde si es tuyo. Los secretos aparecen como «???».
- **`/logros/{id}`, el detalle.** Descripción y condición exacta, rareza de diseño y estadística, cantidad y porcentaje (con las reglas de §2.4), «primero en conseguirlo» o «primer registro», y los últimos en desbloquearlo. Si es tuyo, el contexto: torneo, evento, rival, fecha real, fecha de reconocimiento y evidencia («seed 27 le ganó a seed 3, 3-2»).
- **Ficha del jugador y perfil del Prode:**
  1. **Vitrina** de 3 logros destacados.
  2. «Ahora mismo»: estados dinámicos (Líder, Nuevo, Especialista, Camaleón).
  3. Progreso por categoría y enlace a «Ver todos».
- **Colecciones temáticas:** Multiverso de vBash, Régimen de Spike, Memes de Smash PY, Primeros pasos (`bautismo`, `estreno`, `primer_top8`, `ese_soy_yo`, `first_prode`) y Ediciones. Cada una tiene una barra de avance.

### 5.2 Vitrina
- **La elige el usuario**, desde «Mi cuenta» → «Vitrina». Puede elegir logros de su jugador vinculado y del Prode. Ni administradores ni el sistema la eligen por él.
- Tabla `user_showcase(user_id, slot 1–3, achievement_ref)`, donde la referencia apunta a una fila de `player_achievements` o de `prode_achievements`. Si el logro se revoca, el lugar queda vacío.
- Sin vitrina elegida, o en jugadores sin cuenta: se muestran automáticamente los 3 más raros (por porcentaje), con la leyenda «automática».
- La imagen para compartir del jugador (`/og/player/{id}`) usa la vitrina.

### 5.3 Celular
- Una columna; las tarjetas tienen un alto mínimo de 64 px y el texto se recorta en 2 líneas.
- La vitrina son tres tarjetas cuadradas en fila (≥ 96 px cada una).
- Los filtros son chips en una fila con desplazamiento propio, sin desplazamiento horizontal de la página.
- El detalle se abre como página completa (no modal) para poder compartir el enlace.

### 5.4 Avisos
Al iniciar sesión: «Desbloqueaste 2 logros nuevos» si hay filas con `recognized_at` posterior a la última visita. Los otorgados retroactivamente se agrupan en un único aviso.

## 6. Identidad

### 6.1 Jugador
Los logros de jugador cuelgan de `players.id`, que se resuelve desde el **ID de jugador de start.gg** (`external_identities`). El nametag (`players.tag`, `tag_snapshot`) solo se muestra; nunca identifica. Los cambios de tag (`player_aliases`) no afectan los logros.

### 6.2 Cuenta
Los logros del Prode cuelgan de `users.id`. Una cuenta ve los logros de su jugador mediante su **vínculo activo y verificado** (`player_links`, ADR-021). Desvincular no borra nada: los logros de jugador quedan en el jugador, y los del Prode en la cuenta.

### 6.3 Personas de referencia (Spike, vBash)
- Tabla `achievement_subjects(key, player_id, startgg_player_id, consent_at, set_by, updated_at)`, con claves como `spike` y `vbash`.
- La carga un superadmin indicando el **ID de jugador de start.gg**; el sistema lo resuelve a `players.id` y rechaza la carga si no existe esa identidad.
- **Sin `consent_at`, los logros de esa colección no se evalúan ni se muestran.**
- Las reglas reciben el `player_id` de referencia, nunca un tag. La persona de referencia queda excluida de sus propios logros «contra».
- Los logros contra Spike exigen además: set oficial (elegible), seeds del mismo evento (`event_entrants.seed` de ese evento) y seeding fiable.

## 7. Migraciones aditivas previstas

Una migración (`0024`), aditiva y reversible. No toca datos existentes.

| Cambio | Tipo |
| --- | --- |
| `player_achievements` | Tabla nueva |
| `achievement_stats` | Tabla nueva |
| `achievement_subjects` | Tabla nueva |
| `user_showcase` | Tabla nueva |
| `prode_achievements`: `event_at`, `evidence`, `source`, `rule_version`, `status`, `revoked_at` | Columnas nulas o con valor por defecto |
| `player_achievement_preferences(user_id, achievement_id, public)` para la visibilidad de los logros de humor | Tabla nueva (puede ir en la misma migración) |

Futuras, solo si se aprueban los logros AF: `tournaments.series` y el organizador del torneo en `startgg_tournaments`.

## 8. Rendimiento

- **Cuándo se evalúa:** al terminar una importación o sincronización que cambió sets (el mismo punto donde hoy se llama `insights.engine.invalidate()`), al publicar un ranking, al liquidar un Prode y cada noche como red de seguridad. Nunca en una visita.
- **Cómo:** una pasada en memoria sobre `insights.engine.Data` (ya carga los sets elegibles de la comunidad en una consulta), O(sets), sin consultas por jugador. Con el volumen actual (unos miles de sets) es de segundos.
- **Incremental:** después de la carga inicial, solo se reevalúan los jugadores que aparecen en los eventos que cambiaron, más los logros globales (`destronar`, rankings) cuando se publica un ranking.
- **Lectura:** la ficha hace una consulta indexada por `player_id`; el catálogo lee `achievement_stats`.
- **Compatibilidad:** `GET /insights/players/{id}` sigue devolviendo `badges` con los mismos `id`, `name` y `why`, y `GET /prode/players/{id}/achievements` mantiene su forma. La web actual sigue funcionando sin cambios mientras se construye la nueva.

## 9. Fases sugeridas (fuera de esta misión)

1. Catálogo en código con los 25 existentes, prueba de regresión de los identificadores, `GET /achievements/catalog` y diff en el Prode (sin logros nuevos).
2. Migración `0024`, evaluador de jugador, carga retroactiva marcada y primera tanda T1.
3. Interfaz: `/logros`, detalle, vitrina y estadísticas.
4. Colecciones de Spike y vBash (con consentimiento), manuales y T2.
5. T3 cuando existan los datos.
