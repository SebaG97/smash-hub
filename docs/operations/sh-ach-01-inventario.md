# SH-ACH-01 — Inventario de logros y catálogo propuesto (para aprobación)

Fecha: 12/11/2026. Estado: **propuesta**. No se creó ningún logro nuevo, no se cambió código ni base, no hubo push ni despliegue.

> **Implementado en SH-ACH-01:** ver [sh-ach-01.md](sh-ach-01.md). **Continúa en [docs/logros/](../logros/README.md) (SH-ACH-01A):** el catálogo ampliado y el diseño completo reemplazan las secciones 3, 4, 6 y 7 de este documento. El inventario (secciones 1 y 2) y el glosario (sección 5) siguen vigentes.

Incorpora el complemento obligatorio de SH-ACH-01: preservar los logros existentes, identidad paraguaya y aprobación antes de cargar el catálogo.

## 1. Inventario del sistema actual

Hoy hay **dos sistemas** distintos, con datos y ciclos de vida diferentes.

### 1.1 Logros del Prode (persistidos)

- Reglas: `app/prode/engine.py` (`achievements` por concurso y `lifetime` acumulados). Puras, sin base ni start.gg (ADR-020).
- Tabla `prode_achievements` (migración `0018`): `user_id`, `contest_id` (nulo en acumulados), `kind` (`String(40)`), `title`, `detail`, `rare`, `created_at`. Única por `(user_id, contest_id, kind)`.
- Se otorgan al liquidar (`prode.service.settle`): se **borran y recalculan** todos los del concurso y, después, los acumulados de los participantes (`_lifetime`).
- Se ven en `/prode/u/{id}` (`AchievementList`) y en la ficha del jugador vinculado (`GET /prode/players/{id}/achievements`, ADR-021).
- La web repite el catálogo a mano en `ACHIEVEMENTS` (`apps/web/src/components/prode.tsx`).

| `kind` | Nombre | Condición | Rareza | Alcance |
| --- | --- | --- | --- | --- |
| `oracle` | Oráculo | Acertó al campeón | común | concurso |
| `sharp_eye` | Ojo clínico | Acertó al subcampeón | común | concurso |
| `against_the_tide` | Contra la corriente | Acertó un campeón seed 2–4 | común | concurso |
| `upset_prophet` | Profeta del batacazo | Acertó un campeón seed ≥ 5 | rara | concurso |
| `top8_seer` | Vidente del Top 8 | Acertó los 8 del Top 8 | rara | concurso |
| `full_house` | Pleno | Campeón, subcampeón y Top 8 exactos | rara | concurso |
| `self_belief` | Fe en sí mismo | Se eligió campeón (cuenta vinculada) y no ganó | común | concurso |
| `self_fulfilling` | Profecía autocumplida | Se eligió campeón y ganó | rara | concurso |
| `prode_champion` | Campeón del Prode | 1.º del Prode con puntos > 0 | común | concurso |
| `prode_podium` | Podio del Prode | 2.º o 3.º con puntos > 0 | común | concurso |
| `regular` | Habitué del Prode | ≥ 3 Prodes liquidados jugados | común | acumulado |
| `dynasty` | Dinastía | ≥ 2 Prodes ganados | rara | acumulado |

### 1.2 Emblemas de jugador (derivados, no persistidos)

- Reglas: `app/insights/engine.py` → `player_insights()`; se calculan en memoria desde los sets elegibles de torneos publicados (caché de 5 min). **No hay tabla**: no existen «desbloqueos históricos» guardados, se recalculan siempre.
- Se ven en la ficha del jugador («Emblemas», `PlayerAchievements`) y en la imagen OG del jugador (`/og/player/{id}`, por nombre). El color sale de `BADGE_TONE` por `id`.

| `id` | Nombre | Condición | Tono | ¿Puede perderse? |
| --- | --- | --- | --- | --- |
| `lider` | Líder indiscutible | N.º 1 del ranking publicado | oro | Sí (estado) |
| `trofeos` | Coleccionista de trofeos | ≥ 3 torneos principales ganados (≥ 8 inscriptos) | oro | No |
| `campeon` | Campeón | 1–2 torneos principales ganados | oro | Lo reemplaza `trofeos` |
| `amateur` | Campeón amateur | Ganó un evento secundario (≥ 8) | hueso | No |
| `david` | David contra Goliat | Upset con factor ≥ 3 | fuego | No |
| `remontadas` | Maestro de las remontadas | ≥ 5 sets ganados tras perder la 1.ª partida | fuego | No |
| `racha` | Racha imparable | ≥ 10 sets ganados seguidos | fuego | No |
| `top8` | Siempre en el top 8 | ≥ 5 top 8 en torneos de ≥ 16 | hueso | No |
| `incansable` | Incansable | ≥ 15 torneos jugados | hueso | No |
| `especialista` | Especialista | ≥ 90 % de ≥ 30 partidas con un personaje | hueso | Sí |
| `camaleon` | Camaleón | ≥ 4 personajes con ≥ 5 partidas | hueso | Sí |
| `mes` | Jugador del mes | Ganó al menos un mes en su región | oro | No |
| `nuevo` | Nuevo en la escena | Primer torneo en los últimos 60 días | hueso | Sí (estado) |

«No» supone que los datos importados no cambian; si se despublica un torneo o se corrige un set, el emblema puede desaparecer.

### 1.3 Logros ya otorgados en producción

No se consultó producción (restricción de la misión). Por la documentación: el Prode se desplegó el 11/11/2026 y el primero abierto es el de Center Stage (14/11/2026), todavía sin liquidar. Por lo tanto, **`prode_achievements` debería estar vacía**. Los emblemas no tienen filas.

Para confirmarlo, el propietario puede ejecutar esta consulta de solo lectura:

```sql
SELECT status, count(*) FROM prode_contests GROUP BY status;
SELECT kind, rare, count(*) AS filas, count(DISTINCT user_id) AS usuarios
FROM prode_achievements GROUP BY kind, rare ORDER BY kind;
```

## 2. Hallazgos de compatibilidad

1. **La fecha de desbloqueo no sobrevive a una nueva liquidación.** `settle` borra e inserta: `created_at` pasa a ser la hora de la última liquidación y `_lifetime` reescribe los acumulados de todos los participantes cada vez. Si se agregan reglas y se recalcula, todos los logros «se desbloquean de nuevo» hoy.
2. **El nombre está desnormalizado.** `title` y `detail` se guardan por fila. Cambiar un nombre en el código no cambia las filas existentes hasta volver a liquidar.
3. **El catálogo está duplicado** entre el backend y la web (`ACHIEVEMENTS`, `BADGE_TONE`), y nada verifica que coincidan.
4. **Mezcla de estados y logros.** `lider`, `nuevo`, `especialista` y `camaleon` describen el presente y pueden perderse; el resto son hitos. Hoy se muestran juntos.
5. **Dos escalas de rareza:** booleano `rare` (Prode) y tono oro/fuego/hueso (emblemas).

## 3. Qué se conserva, qué se amplía y qué se incorpora

**Se conserva sin cambios**
- Los 12 `kind` del Prode y los 13 `id` de emblemas, con sus condiciones actuales.
- La tabla `prode_achievements`, su restricción única, las rutas de la API y los componentes `AchievementList` y `PlayerAchievements`.
- Los nombres visibles actuales. Cualquier cambio de nombre solo afecta la presentación, nunca el identificador (sección 6, decisión D4).

**Se amplía**
- `prode/engine.py`: reglas nuevas del Prode en la misma tabla y el mismo flujo de liquidación.
- `insights/engine.py`: emblemas nuevos de jugador con `id` estables.
- El recálculo del Prode conserva `created_at` de las filas que ya existían (upsert por `(user_id, contest_id, kind)` en vez de borrar todo). Así se corrige el hallazgo 1.

**Se incorpora**
- Un catálogo único en el backend (`app/achievements/catalog.py`): `id`, alcance (`prode` | `jugador`), tipo (`logro` | `estado`), nombre, descripción, condición legible, categoría, rareza (común, poco común, rara, épica) y origen del nombre. Es código, no una tabla: no hay nombres que «cargar» en la base.
- `GET /api/v1/achievements/catalog`, para que la web deje de repetir `ACHIEVEMENTS` y `BADGE_TONE`.
- Rareza de 4 niveles en el catálogo. Compatibilidad: `rare = true` en `prode_achievements` equivale a rara o épica, sin migración.

## 4. Diseño técnico propuesto

1. **Catálogo** (`app/achievements/catalog.py`) con las 25 entradas existentes, tal como están. Prueba de regresión: todos los `kind`/`id` actuales siguen presentes, son únicos y miden ≤ 40 caracteres.
2. **API** `GET /achievements/catalog` (pública, cacheable). La web lo usa en `/prode` y en la ficha del jugador. Si falla, se muestra lo que ya trae cada logro (`title`, `name`), como hoy.
3. **Presentación por catálogo:** el nombre visible sale del catálogo por `kind`; `title` guardado queda como respaldo. Permite renombrar sin reescribir filas.
4. **Prode:** reglas nuevas en `engine.achievements`/`engine.lifetime` (puras, con pruebas unitarias). `settle` pasa a upsert para conservar fechas. Nuevo `rebuild_achievements(contest)` recalcula desde los resultados ya guardados en `prode_questions.result`, sin llamar a start.gg. Solo un administrador lo ejecuta, con auditoría.
5. **Emblemas:** nuevas reglas en `player_insights()`, con el campo `type` (`logro`/`estado`) del catálogo. La ficha separa «Emblemas» de «Ahora mismo» (estados).
6. **Persistencia de emblemas (opcional, decisión D2):** una tabla `player_achievements(player_id, id, first_earned_at, detail)` permitiría conservar la fecha del primer desbloqueo y avisar logros nuevos. No es necesaria para la fase 1.
7. **Documentación al implementar:** ADR-023 (sistema de logros), `docs/architecture/prode.md`, `docs/statistics.md` y, si se aprueba D2, `docs/database/schema.md` y una migración aditiva.

## 5. Identidad paraguaya: términos y nivel de certeza

| Nivel | Términos | Criterio |
| --- | --- | --- |
| **A. Conocidos y seguros** | *nde* / *¡ndeee!* (sorpresa), *purete* (excelente), *jopará* (mezcla), *che ra'a* (amigo), *ñande* (nosotros, incluyente), tereré y ronda de tereré, *Pombero* (mito nocturno), *infaltable* | De uso general y documentado. Se usan con su sentido real. |
| **B. Guaraní a validar** | *mbarete* (fuerte, poderoso), *py'aguasu* (valiente), *kane'õ* (cansado), *tujá* (viejo, afectuoso), *paje* (hechizo, «le hicieron paje») | Creo que el sentido es correcto, pero la búsqueda no lo confirmó. Revisarlo con hablantes antes de publicar, en particular la grafía. |
| **C. Inventados para Smash Hub** | «Por la puerta de atrás», «Dueño del pool», «Ruta PY02», «Siempre en la ronda», «Doble función», «Contra el pueblo» | Frases en español con sentido competitivo, sin pretender ser expresiones existentes. |
| **D. Memes de Smash PY sin verificar** | *kp*, «Nde ru» (versión del «soy tu padre») | **No pude confirmar qué significa «kp»** en Paraguay. «Nde ru» es humor de burla: necesita aprobación de la comunidad. No se usan hasta validarlos. |

Descartados: *añamemby* y otros insultos, *vai vai*/*tavy* como nombres de logro (señalan al que pierde), Kurupí (connotación sexual), y la comida típica sin relación competitiva.

## 6. Catálogo propuesto

Datos: **S** = sets con seeds, ronda y puntaje (`sets`, `set_sides`), **P** = posiciones (`event_entrants`), **G** = personajes por partida (`set_selections`), **T** = torneo (fecha, ciudad), **E** = equipos/prefijos, **PR** = Prode. Todos se calculan automáticamente, salvo que se indique lo contrario.

### Torneos y bracket (emblemas de jugador)

| # | `id` | Nombre | Descripción | Condición exacta | Rareza | Datos | Equivalente | Validar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `mbarete` | Mbarete | Campeón sin perder un set | Ganó un torneo principal de ≥ 16 inscriptos sin perder ningún set en ese evento | épica | S, P | Amplía `campeon` | B |
| 2 | `back_door` | Por la puerta de atrás | Campeón desde losers | Ganó un torneo principal de ≥ 16 inscriptos después de perder un set en ese evento | rara | S, P | Nuevo | — |
| 3 | `purete` | Purete | Gran final sin perder una partida | Ganó la gran final (`round_label` de gran final) sin ceder ninguna partida, en un set al mejor de 3 o 5 | rara | S | Nuevo | A; requiere que el nombre de la ronda sea fiable |
| 4 | `ndeee` | ¡Ndeee! | El upset que nadie vio venir | Ganó un set con factor de upset ≥ 5 | rara | S | Amplía `david` (factor ≥ 3), que se mantiene | A |
| 5 | `py_aguasu` | Py'aguasu | Terminó muy por encima de su seed | En un torneo de ≥ 16, terminó ≥ 3 tramos mejor que su seed (ya se calcula en «Mejor rendimiento») | poco común | S, P | Usa el récord `best_overperformance`, sin emblema hoy | B |
| 6 | `pool_owner` | Dueño del pool | Ganó todo su pool | Ganó todos sus sets de una pool con ≥ 4 jugadores | poco común | S, fases | Nuevo; depende de la copia de pools (SH-SYNC-01) | — |
| 7 | `kane_o` | Kane'õ | Run larga en un solo torneo | Jugó ≥ 8 sets en un mismo evento | común | S | Nuevo | B |
| 8 | `runback` | Runback | Revancha en el mismo torneo | Perdió con un rival y le ganó después en el mismo evento | poco común | S | Nuevo | — |
| 9 | `pombero` | Pombero | Gana cuando todos duermen | Ganó un set completado entre 00:00 y 04:00 (hora de Asunción) | poco común | S (`completed_at`) | Nuevo | A; la hora de start.gg puede ser la de carga del resultado |

### Rivalidades y comunidad

| # | `id` | Nombre | Descripción | Condición exacta | Rareza | Datos | Equivalente | Validar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | `che_raa` | Che ra'a | Rival de toda la vida | Jugó ≥ 10 sets contra el mismo jugador | común | S | Usa el récord `main_rival` | A |
| 11 | `nde_ru` | Nde ru | Le tiene la mano cambiada | Ganó ≥ 5 sets seguidos a un mismo rival sin perder ninguno entre ellos | rara | S | Nuevo | **D: comunidad** |
| 12 | `tuja` | Tujá de la escena | Veterano | ≥ 2 años entre su primer y último torneo y ≥ 20 torneos | poco común | T, P | Amplía `incansable` (15) | B |
| 13 | `ronda` | Siempre en la ronda | No falta a ninguna juntada | Jugó ≥ 4 torneos publicados en un mismo mes calendario | poco común | T | Nuevo | C |
| 14 | `ruta_py02` | Ruta PY02 | Jugó en las dos regiones | Jugó torneos en Gran Asunción y en Ciudad del Este (`REGIONS`) | poco común | T (ciudad) | Nuevo | C; depende de que la ciudad del torneo esté cargada |
| 15 | `nande` | Ñande | El equipo copó el top 8 | ≥ 3 integrantes del mismo equipo en el top 8 de un torneo de ≥ 16 (se otorga a cada uno) | rara | P, E | Nuevo | A; depende de los prefijos |

### Personajes

| # | `id` | Nombre | Descripción | Condición exacta | Rareza | Datos | Equivalente | Validar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16 | `jopara` | Jopará | Mezcló personajes y ganó | Ganó un set usando ≥ 3 personajes distintos | poco común | G | Complementa `camaleon` (frecuencia, no un set) | A |

### Prode (misma tabla `prode_achievements`)

| # | `kind` | Nombre | Descripción | Condición exacta | Rareza | Datos | Equivalente | Validar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 17 | `almost_full` | Por un pelo | Casi el Top 8 perfecto | Acertó 7 de los 8 del Top 8 | poco común | PR | Escalón previo a `top8_seer` | — |
| 18 | `against_the_crowd` | Contra el pueblo | Acertó lo que casi nadie vio | Acertó al campeón cuando lo eligió ≤ 10 % de los pronosticadores del concurso (≥ 10 participantes) | rara | PR | Distinto de `upset_prophet` (seed, no popularidad) | — |
| 19 | `paje` | Paje | Racha de campeones acertados | Acertó al campeón en 3 Prodes liquidados consecutivos en los que participó | épica | PR | Amplía `oracle` (acumulado) | B |
| 20 | `infaltable` | Infaltable | No se pierde un Prode | ≥ 10 Prodes liquidados jugados | rara | PR | Amplía `regular` (3), que se mantiene | A |
| 21 | `double_duty` | Doble función | Jugó el torneo y ganó el Prode | Su cuenta vinculada jugó el evento y terminó 1.º en el Prode | rara | PR, P, vínculo | Nuevo | — |

### No medibles (solo manuales; no se proponen para la fase 1)

- «Tereré rupa» (llegar primero al venue), «Cebador oficial» (aportar el termo), «Anfitrión» (prestar setup). Requerirían que un organizador los otorgue a mano: un sistema distinto, con abuso posible. Recomiendo dejarlos fuera.

## 7. Decisiones pendientes

- **D1. Catálogo:** aprobar, quitar o renombrar cada candidato (1–21). Indicar memes reales de Smash PY para reemplazar los del nivel D.
- **D2. Persistencia de emblemas:** fase 1 sin tabla (recomendado) o tabla `player_achievements` con fecha del primer desbloqueo.
- **D3. Upsert al liquidar** para conservar fechas de los logros del Prode (recomendado).
- **D4. Nombres existentes:** mantenerlos (recomendado) o reemplazar alguno por un nombre local, solo en la presentación y sin cambiar el `kind`/`id`.
- **D5. Validación lingüística** de los términos del nivel B con alguien de la comunidad que hable guaraní.
