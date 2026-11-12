# Catálogo de logros de Smash Hub (SH-ACH-01A)

Estado: **implementado** (SH-ACH-01). El catálogo vive en `apps/api/app/achievements/catalog.py`, que es la fuente de verdad. Diseño: [diseno.md](diseno.md). Resumen y decisiones: [README.md](README.md). Qué está activo y por qué: [operations/sh-ach-01.md](../operations/sh-ach-01.md#2-logros-activos).

### Estado de la implementación respecto de esta propuesta

- **Activos (53 nuevos):** toda la primera tanda (T1, 28) y los T2 con datos fiables: `reset_y_corona`, `purete`, `barrida`, `reverse_3_0`, `cincuenta_brackets`, `trescientos`, `nunca_muerto`, `tricampeon_mes`, `constancia`, `volvio`, `conoce_a_todos`, `jopara`, `clasico`, `paje`, `early_bird`, `last_minute`, `jinx`, `podium_streak`, `en_bici_hasta_cde`, `la_mufa_no_funciona`, `pombero`, `nerfeado_por_la_trama`, `los_johns`, `independencia` y `coleccionista`.
- **Preparados y desactivados hasta tener identidad y consentimiento (9):** los automáticos de Spike y de vBash, incluido `todos_somos_vbash`.
- **Pasaron a pendientes respecto de la propuesta:** `fue_numero_uno`, `top10_ranking`, `escalador` y `destronar` (no hay un historial verificable de publicaciones del ranking); `nande` (sin historial de prefijos por torneo); `estuve_ahi` (falta marcar ediciones); `fundador` (es de cuenta).
- **Ajustes de condición:**
  - `primer_top8` y `fijo_top8` usan posición ≤ 8, igual que el emblema existente `top8`.
  - `puerta_de_atras` exige llegar a la gran final desde la final de losers.
  - `golpe_de_estado` exige que sea el último set de Spike en el evento.
  - `casi_kp` usa el último set del subcampeón contra el campeón (la gran final decisiva).
- **Rareza visible:** sale de este catálogo. La columna `prode_achievements.rare` se conserva sin cambios.

## Leyenda

| Campo | Valores |
| --- | --- |
| **Rar.** (rareza de diseño) | **C** común · **R** raro · **É** épico · **L** legendario |
| **Datos** | **S** sets elegibles (seeds, puntaje, orden, hora) · **P** posiciones finales · **G** personajes por partida · **T** torneo (fecha, ciudad, tamaño, evento principal) · **E** equipos/prefijos · **RK** rankings publicados · **PL** pools y fases (copia de start.gg) · **PR** Prode · **CU** cuentas y vínculos · **ID** identidad de referencia por ID de start.gg · **AD** decisión de la organización |
| **Disp.** (disponibilidad real) | **✔** histórico completo · **◐** parcial (ver nota) · **✗** no existe hoy |
| **Viab.** | **A0** automático ahora · **AF** automático futuro (falta un dato) · **M** manual · **PD** pendiente de definición o validación |
| **Tipo** | **P** permanente · **E** estado dinámico · **Lim** edición limitada |
| **Sec.** | **sí** = secreto hasta desbloquearlo · **h** = humor: lo ve su dueño y es público solo si lo elige (diseño §3.4) |
| **Origen** | **EX** existente · **CR** idea creativa · **PY** expresión paraguaya (A segura / B a validar) · **MC** meme de Smash PY aportado por la organización · **MV** meme a validar |
| **Prio.** | **T1** primera tanda · **T2** segunda · **T3** cuando exista el dato o la validación |

### Reglas comunes (se aplican a todos los logros de bracket)

- Solo cuentan los sets **elegibles** (`sets.stats_eligible`: jugados, sin DQ ni bye) de **torneos publicados**.
- «Evento principal» = rol `main` (`app/competitions/roles.py`: decisión del organizador o regla automática).
- Todo lo que use seeds exige `tournaments.seeding_reliable = true` y seeds **del mismo evento**, igual que los emblemas actuales.
- «Inscriptos» = `events.num_entrants`. «Tramo» = `insights.engine.tier()` (1, 2, 3, 4, 5, 7, 9, 13…).
- El jugador se identifica por `players.id`, que se resuelve desde el **ID de jugador de start.gg** (`external_identities`), nunca por el nametag.
- Las fechas se evalúan en hora de Asunción (`America/Asuncion`).

---

## 1. Los 25 logros existentes (se conservan sin cambios)

Se mantienen identificador, nombre y condición. Solo se les asigna categoría, rareza de diseño y tipo **para presentación**. La columna `rare` del Prode no se reescribe.

| ID | Nombre | Condición actual | Sistema | Categoría | Rar. | Tipo | `rare` hoy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `oracle` | Oráculo | Acertó al campeón | Prode | Prode | C | P | no |
| `sharp_eye` | Ojo clínico | Acertó al subcampeón | Prode | Prode | C | P | no |
| `against_the_tide` | Contra la corriente | Campeón acertado, seed 2–4 | Prode | Prode | C | P | no |
| `upset_prophet` | Profeta del batacazo | Campeón acertado, seed ≥ 5 | Prode | Prode | R | P | sí |
| `top8_seer` | Vidente del Top 8 | 8 de 8 del Top 8 | Prode | Prode | É | P | sí |
| `full_house` | Pleno | Campeón, subcampeón y Top 8 exactos | Prode | Prode | L | P | sí |
| `self_belief` | Fe en sí mismo | Se eligió campeón y no ganó | Prode | Prode | C | P | no |
| `self_fulfilling` | Profecía autocumplida | Se eligió campeón y ganó | Prode | Prode | É | P | sí |
| `prode_champion` | Campeón del Prode | 1.º del Prode con puntos | Prode | Prode | R | P | no |
| `prode_podium` | Podio del Prode | 2.º o 3.º con puntos | Prode | Prode | C | P | no |
| `regular` | Habitué del Prode | ≥ 3 Prodes liquidados | Prode | Prode | C | P | no |
| `dynasty` | Dinastía | ≥ 2 Prodes ganados | Prode | Prode | É | P | sí |
| `lider` | Líder indiscutible | N.º 1 del ranking publicado | Emblema | Trayectoria | L | **E** | — |
| `trofeos` | Coleccionista de trofeos | ≥ 3 principales ganados (≥ 8) | Emblema | Competitivos | É | P | — |
| `campeon` | Campeón | 1–2 principales ganados (≥ 8) | Emblema | Competitivos | R | P | — |
| `amateur` | Campeón amateur | Ganó un evento secundario (≥ 8) | Emblema | Competitivos | C | P | — |
| `david` | David contra Goliat | Upset con factor ≥ 3 | Emblema | Competitivos | R | P | — |
| `remontadas` | Maestro de las remontadas | ≥ 5 sets ganados tras perder la 1.ª partida | Emblema | Trayectoria | R | P | — |
| `racha` | Racha imparable | ≥ 10 sets seguidos | Emblema | Trayectoria | É | P | — |
| `top8` | Siempre en el top 8 | ≥ 5 top 8 en torneos de ≥ 16 | Emblema | Trayectoria | R | P | — |
| `incansable` | Incansable | ≥ 15 torneos | Emblema | Trayectoria | R | P | — |
| `especialista` | Especialista | ≥ 90 % de ≥ 30 partidas con un personaje | Emblema | Trayectoria | C | **E** | — |
| `camaleon` | Camaleón | ≥ 4 personajes con ≥ 5 partidas | Emblema | Trayectoria | C | **E** | — |
| `mes` | Jugador del mes | Ganó al menos un mes en su región | Emblema | Trayectoria | É | P | — |
| `nuevo` | Nuevo en la escena | Primer torneo en los últimos 60 días | Emblema | Trayectoria | C | **E** | — |

Notas:
- `campeon` y `trofeos` son un escalón: hoy el segundo **reemplaza** al primero en la ficha. En el sistema nuevo se guardan los dos (se mantiene el `id`) y la ficha puede seguir mostrando solo el mayor.
- De los 21 candidatos de SH-ACH-01 se conservan 20, algunos ajustados: `back_door` pasa a `puerta_de_atras`, `ronda` a `siempre_en_la_ronda` y `pool_owner` a `dueno_del_pool` (T3, por falta de pools históricos); «Pombero» pasa a secreto. «Ruta PY02» se reemplaza por «En bici hasta CDE».

---

## 2. Logros nuevos

IDs nuevos: `snake_case` en español sin tildes para logros de jugador (como los emblemas actuales) y en inglés para el Prode (como los `kind` actuales), con un máximo de 40 caracteres.

### 2.1 Competitivos y brackets

| # | ID | Nombre | Descripción | Condición exacta | Rar. | Datos | Disp. | Viab. | Tipo | Equivalente | Sec. | Origen | Prio. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `mbarete` | Mbarete | Campeón sin perder un set | Ganó un evento principal de ≥ 16 inscriptos sin perder ningún set elegible en ese evento | É | S, P | ✔ | A0 | P | Amplía `campeon` | — | PY-B | T1 |
| 2 | `puerta_de_atras` | Por la puerta de atrás | Campeón desde losers | Ganó un evento principal de ≥ 16 habiendo perdido exactamente un set en ese evento | R | S, P | ✔ | A0 | P | — | — | CR | T1 |
| 3 | `reset_y_corona` | Reset y corona | Ganó la gran final con reset | Campeón de un principal de ≥ 16 cuyos dos últimos sets fueron contra el mismo rival y perdió el primero | É | S, P | ✔ | A0 | P | — | — | CR | T2 |
| 4 | `purete` | Purete | Final impecable | Campeón de un principal de ≥ 16 que ganó su último set (al mejor de 3 o 5) sin ceder partidas | R | S, P | ✔ | A0 | P | — | — | PY-A | T2 |
| 5 | `ndeee` | ¡Ndeee! | El upset que nadie vio venir | Ganó un set con factor de upset ≥ 5 | É | S | ✔ | A0 | P | Amplía `david` (≥ 3) | — | PY-A | T1 |
| 6 | `py_aguasu` | Py'aguasu | Terminó muy por encima de su seed | En un principal de ≥ 16: `tier(seed) − tier(posición) ≥ 3` | R | S, P | ✔ | A0 | P | Hoy solo es el récord «Mejor rendimiento» | — | PY-B | T1 |
| 7 | `primer_podio` | Al podio | Primer top 3 | Terminó 1.º–3.º en un principal de ≥ 16 | C | P | ✔ | A0 | P | — | — | CR | T1 |
| 8 | `primer_top8` | Bienvenido al top 8 | Primer top 8 | Terminó ≤ 7.º en un principal de ≥ 16 | C | P | ✔ | A0 | P | Escalón previo a `top8` | — | CR | T1 |
| 9 | `desde_el_fondo` | Desde el fondo del seeding | Top 8 desde muy abajo | Top 8 de un principal de ≥ 32 siendo seed ≥ 25 | É | S, P | ✔ | A0 | P | — | — | CR | T1 |
| 10 | `barrida` | Barrida | 3-0 cuando más importa | Ganó 3-0 un set al mejor de 5 contra un rival que terminó en el top 8 del mismo evento | R | S, P | ✔ | A0 | P | — | — | CR | T2 |
| 11 | `reverse_3_0` | Reverse 3-0 | Perdía 0-2 y lo dio vuelta | Ganó 3-2 un set al mejor de 5 habiendo perdido las partidas 1 y 2 | É | G | ◐ solo sets con partidas reportadas | A0 | P | Amplía `remontadas` | — | CR | T2 |
| 12 | `kane_o` | Kane'õ | Una run larguísima | Jugó ≥ 8 sets elegibles en un mismo evento | C | S | ✔ | A0 | P | — | — | PY-B | T1 |
| 13 | `runback` | Runback | Revancha en el mismo torneo | Perdió un set contra un rival y le ganó un set posterior en el mismo evento | R | S | ✔ | A0 | P | — | — | CR | T1 |
| 14 | `doble_corona` | Doble corona | Dos títulos en un mes | Ganó dos eventos principales (≥ 8) en el mismo mes calendario | É | P, T | ✔ | A0 | P | — | — | CR | T1 |
| 15 | `bicampeon` | Bicampeón | Defendió el título | Ganó dos ediciones consecutivas de la misma serie de torneos | É | P, T | ✗ no hay «serie» de torneos | AF | P | — | — | CR | T3 |
| 16 | `graduado` | Graduado | De amateur al top 8 | Ganó un evento secundario (≥ 8) y, en un torneo posterior, hizo top 8 en un principal de ≥ 16 | R | P, T | ✔ | A0 | P | Amplía `amateur` | — | CR | T1 |
| 17 | `estreno` | Estreno | Primer set ganado | Ganó su primer set elegible | C | S | ✔ | A0 | P | — | — | CR | T1 |
| 18 | `dueno_del_pool` | Dueño del pool | Ganó todo su pool | Ganó todos sus sets en un pool de la primera fase con ≥ 4 jugadores | C | PL | ◐ solo torneos seguidos desde SH-SYNC-01 | AF | P | — | — | CR | T3 |
| 19 | `esta_vez_si` | Esta vez sí | Por fin pasó pools | Pasó la fase de pools en un evento después de no pasarla en su evento anterior con pools | R | PL | ◐ igual que el anterior | AF | P | — | — | MC | T3 |

### 2.2 Trayectoria y estadísticas

| # | ID | Nombre | Descripción | Condición exacta | Rar. | Datos | Disp. | Viab. | Tipo | Equivalente | Sec. | Origen | Prio. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | `bautismo` | Bautismo | Primer torneo oficial | Jugó al menos un set elegible en un torneo publicado | C | S, T | ✔ | A0 | P | Contraparte permanente de `nuevo` | — | CR | T1 |
| 21 | `de_la_casa` | Ya es de la casa | Cinco torneos | Jugó ≥ 5 torneos | C | T | ✔ | A0 | P | Escalón previo a `incansable` (15) | — | CR | T1 |
| 22 | `tuja` | Tujá de la escena | Veterano de verdad | ≥ 2 años entre su primer y su último torneo y ≥ 30 torneos | É | T | ✔ | A0 | P | Amplía `incansable` | — | PY-B | T1 |
| 23 | `cincuenta_brackets` | Cincuenta brackets | Una vida en la escena | Jugó ≥ 50 torneos | L | T | ✔ | A0 | P | Amplía `incansable` | — | CR | T2 |
| 24 | `medio_centenar` | Medio centenar | 50 sets ganados | ≥ 50 sets elegibles ganados | C | S | ✔ | A0 | P | — | — | CR | T1 |
| 25 | `trescientos` | Trescientos | 300 sets ganados | ≥ 300 sets elegibles ganados | É | S | ✔ | A0 | P | — | — | CR | T2 |
| 26 | `aplanadora` | Aplanadora | Veinte seguidos | ≥ 20 sets ganados seguidos | L | S | ✔ | A0 | P | Amplía `racha` (10) | — | CR | T1 |
| 27 | `nunca_muerto` | Nunca muerto | Especialista en remontar | ≥ 20 sets ganados tras perder la 1.ª partida | É | S, G | ◐ misma fuente que `remontadas` | A0 | P | Amplía `remontadas` (5) | — | CR | T2 |
| 28 | `fijo_top8` | Fijo en el top 8 | Siempre está | ≥ 15 top 8 en torneos de ≥ 16 | É | P | ✔ | A0 | P | Amplía `top8` (5) | — | CR | T1 |
| 29 | `fue_numero_uno` | Fue el número 1 | Estuvo en la cima | Fue 1.º en alguna publicación de un ranking | L | RK | ◐ solo publicaciones guardadas en `ranking_snapshots` | A0 | P | Contraparte permanente de `lider` | — | CR | T2 |
| 30 | `top10_ranking` | Top 10 | Entre los mejores | Apareció en el top 10 de alguna publicación de un ranking | R | RK | ◐ | A0 | P | — | — | CR | T2 |
| 31 | `escalador` | Escalador | Subida fuerte | Subió ≥ 10 posiciones entre dos publicaciones consecutivas del mismo ranking | R | RK | ◐ | A0 | P | — | — | CR | T2 |
| 32 | `tricampeon_mes` | Tricampeón del mes | Tres meses en la cima | Jugador del mes ≥ 3 veces | É | S, P, T | ✔ | A0 | P | Amplía `mes` | — | CR | T2 |
| 33 | `constancia` | Constancia | Seis meses sin faltar | ≥ 1 torneo por mes durante 6 meses calendario seguidos | R | T | ✔ | A0 | P | — | — | CR | T2 |
| 34 | `volvio` | Volvió el que faltaba | El regreso | Jugó un torneo después de ≥ 180 días sin jugar ninguno | C | T | ✔ | A0 | P | — | — | CR | T2 |
| 35 | `conoce_a_todos` | Conoce a todos | Cincuenta rivales distintos | Jugó sets elegibles contra ≥ 50 rivales distintos | R | S | ✔ | A0 | P | — | — | CR | T2 |
| 36 | `jopara` | Jopará | Mezcló y ganó | Ganó un set usando ≥ 3 personajes distintos | R | G | ◐ solo sets con personajes reportados | A0 | P | Complementa `camaleon` | — | PY-A | T2 |

### 2.3 Rivalidades

| # | ID | Nombre | Descripción | Condición exacta | Rar. | Datos | Disp. | Viab. | Tipo | Equivalente | Sec. | Origen | Prio. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 37 | `che_raa` | Che ra'a | Rival de toda la vida | ≥ 10 sets elegibles contra el mismo jugador | C | S | ✔ | A0 | P | Usa el récord `main_rival` | — | PY-A | T1 |
| 38 | `clasico` | Clásico | Rivalidad pareja | ≥ 20 sets contra el mismo rival y cada uno ganó ≥ 40 % | É | S | ✔ | A0 | P | — | — | CR | T2 |
| 39 | `exorcismo` | Exorcismo | Se cortó la maldición | Le ganó a un rival después de ≥ 5 derrotas seguidas contra él | É | S | ✔ | A0 | P | — | — | CR | T1 |
| 40 | `nde_ru` | Nde ru | Le tiene la mano cambiada | Ganó ≥ 5 sets seguidos al mismo rival sin perder ninguno entre ellos | R | S | ✔ | PD | P | — | h | MV | T3 |
| 41 | `destronar` | Destronar | Le ganó al número 1 | Ganó un set a quien era 1.º del ranking vigente en la fecha del set | É | S, RK | ◐ | A0 | P | — | — | CR | T2 |
| 42 | `el_seeding_nos_odia` | El seeding nos odia | Siempre el mismo pool | Coincidió en el mismo pool con el mismo rival en 3 eventos | R | PL | ◐ | AF | P | — | — | MC | T3 |

### 2.4 Prode (misma tabla `prode_achievements`)

| # | `kind` | Nombre | Descripción | Condición exacta | Rar. | Datos | Disp. | Viab. | Tipo | Equivalente | Sec. | Origen | Prio. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 43 | `first_prode` | Primer pronóstico | Debutó en el Prode | Participó en su primer Prode liquidado | C | PR | ✔ | A0 | P | Escalón previo a `regular` | — | CR | T1 |
| 44 | `almost_full` | Por un pelo | Casi el Top 8 perfecto | Acertó 7 de los 8 del Top 8 | R | PR | ✔ | A0 | P | Escalón previo a `top8_seer` | — | CR | T1 |
| 45 | `against_the_crowd` | Contra el pueblo | Vio lo que nadie vio | Acertó al campeón cuando lo eligió ≤ 10 % de los participantes (≥ 10 participantes) | É | PR | ✔ | A0 | P | Distinto de `upset_prophet` (popularidad, no seed) | — | CR | T1 |
| 46 | `paje` | Paje | Racha de campeones | Acertó al campeón en 3 Prodes liquidados consecutivos en los que participó | L | PR | ✔ | A0 | P | Amplía `oracle` | — | PY-B | T2 |
| 47 | `infaltable` | Infaltable | No se pierde ninguno | ≥ 10 Prodes liquidados | R | PR | ✔ | A0 | P | Amplía `regular` | — | PY-A | T1 |
| 48 | `double_duty` | Doble función | Jugó el torneo y ganó el Prode | Su jugador vinculado era candidato inscripto del evento y él terminó 1.º en el Prode | É | PR, CU | ✔ | A0 | P | — | — | CR | T1 |
| 49 | `early_bird` | Madrugador | Pronosticó apenas abrió | Su primer pronóstico se guardó ≤ 1 h después de abrirse el Prode | C | PR | ✔ | A0 | P | — | — | CR | T2 |
| 50 | `last_minute` | Sobre la hora | Último minuto y podio | Guardó su último cambio en los 10 min previos al cierre y terminó en el podio del Prode | R | PR | ✔ | A0 | P | — | sí | CR | T2 |
| 51 | `jinx` | Mufa confirmada | Su campeón no llegó | El campeón que eligió terminó fuera del top 8 | C | PR | ✔ | A0 | P | — | h | MC | T2 |
| 52 | `podium_streak` | Siempre en el podio | Tres podios seguidos | Podio del Prode en 3 Prodes consecutivos en los que participó | É | PR | ✔ | A0 | P | Amplía `prode_podium` | — | CR | T2 |
| 53 | `season_champion` | Campeón de temporada | El mejor del año | 1.º de la tabla anual del Prode | L | PR | ◐ no hay temporadas definidas | AF | Lim | — | — | CR | T3 |

### 2.5 Comunidad paraguaya

| # | ID | Nombre | Descripción | Condición exacta | Rar. | Datos | Disp. | Viab. | Tipo | Equivalente | Sec. | Origen | Prio. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 54 | `en_bici_hasta_cde` | En bici hasta CDE | Jugó en las dos regiones | Jugó torneos en Gran Asunción y en Ciudad del Este (`insights.REGIONS`) | R | T | ◐ depende de la ciudad cargada | A0 | P | — | — | MC | T2 |
| 55 | `siempre_en_la_ronda` | Siempre en la ronda | No falta a ninguna juntada | ≥ 4 torneos en un mismo mes calendario | R | T | ✔ | A0 | P | — | — | CR | T1 |
| 56 | `nande` | Ñande | El equipo copó el top 8 | ≥ 3 integrantes del mismo equipo (prefijo aprobado) en el top 8 de un principal de ≥ 16 (para cada uno) | É | P, E | ◐ prefijos desde la misión 15 | A0 | P | — | — | PY-A | T2 |
| 57 | `ese_soy_yo` | Ese soy yo | Cuenta vinculada | Tiene un vínculo activo y verificado entre su cuenta y su jugador | C | CU | ✔ | A0 | P | — | — | CR | T1 |
| 58 | `terere_rupa` | Tereré rupa | El primero en anotarse | Fue el primer inscripto detectado de un torneo | C | PL | ◐ la hora es la de detección del hub, no la de inscripción | PD | P | — | — | PY-A | T3 |
| 59 | `estuve_ahi` | Estuve ahí | Jugó un torneo histórico | Jugó un torneo marcado como especial por la organización (una variante por edición, p. ej. Center Stage 2026) | R | T, AD | ✔ cuando se marca | A0 | Lim | — | — | CR | T2 |
| 60 | `fundador` | Fundador | De los primeros en Smash Hub | Cuenta creada antes del 31/12/2026 | C | CU | ✔ | A0 | Lim | — | — | CR | T2 |
| 61 | `anfitrion` | Anfitrión | Puso el setup | Prestó setup o venue a un torneo (lo registra la organización) | R | AD | ✗ | M | P | — | — | CR | T3 |
| 62 | `la_mufa_no_funciona` | La mufa no funciona | Todos lo daban ganador… y ganó | Ganó el evento principal siendo el campeón más elegido de su Prode (≥ 40 % de los pronósticos, ≥ 10 participantes) | É | PR, P, ID | ✔ | A0 | P | — | — | MC | T2 |

### 2.6 Multiverso de vBash

Requisito: la organización registra a vBash como **persona de referencia** por su ID de jugador de start.gg (diseño §6.3), con su consentimiento. start.gg **no informa colores** de personajes y la base solo guarda el color preferido de cada jugador para las imágenes (`players.costumes`), no el usado en cada partida. Por eso ningún logro automático depende del color.

| # | ID | Nombre | Descripción | Condición exacta | Rar. | Datos | Disp. | Viab. | Tipo | Equivalente | Sec. | Origen | Prio. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 63 | `todos_somos_vbash` | Todos somos vBash | Se sumó al multiverso | Jugó ≥ 10 partidas con Yoshi | C | G | ◐ | A0 | P | — | — | MC | T2 |
| 64 | `que_vbash_sos` | ¿Qué vBash sos? | Le ganó al original con su arma | Le ganó un set a vBash usando Yoshi en al menos una partida ganada | É | G, ID | ◐ | A0 | P | — | — | MC | T2 |
| 65 | `vbash_contra_vbash` | vBash contra vBash | Duelo de Yoshis | Ganó un set en el que los dos usaron solo Yoshi | R | G | ◐ | A0 | P | — | — | MC | T2 |
| 66 | `el_verdadero_vbash` | El verdadero vBash | Hay uno solo | Único: se otorga a vBash una vez confirmada su identidad | L | ID, AD | ✔ | M | P | — | — | MC | T2 |
| 67 | `vbash_rojo` | vBash rojo | El del otro color | Ganó un set con Yoshi rojo | É | color por partida | ✗ | AF | P | — | sí | MC | T3 |
| 68 | `bvash` | bVash | Otra variante | Pendiente de definir con la comunidad, sin usar el nametag | — | — | — | PD | — | — | sí | MC | T3 |
| 69 | `multiverso_vbash` | El multiverso de vBash | Coleccionó el multiverso | Obtuvo 3 logros de esta colección | É | meta | ✔ | A0 | P | — | — | MC | T2 |

### 2.7 Régimen de Spike

Requisitos: Spike registrado como **persona de referencia** por su ID de jugador de start.gg, con su consentimiento. El set tiene que ser **oficial** (elegible), con **seeds del mismo evento** y seeding fiable. Spike queda excluido de los logros de esta colección que son contra él.

| # | ID | Nombre | Descripción | Condición exacta | Rar. | Datos | Disp. | Viab. | Tipo | Equivalente | Sec. | Origen | Prio. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 70 | `dictador_caido` | El Dictador ha Caído | Le ganó a Spike | Ganó un set oficial a Spike teniendo peor seed que él en ese evento | É | S, ID | ✔ | A0 | P | Caso particular de `david` | — | MC | T1* |
| 71 | `golpe_de_estado` | Golpe de Estado | Eliminó a Spike | Ganó el último set de Spike en un evento (el que lo eliminó) teniendo peor seed | L | S, ID | ✔ | A0 | P | — | — | MC | T1* |
| 72 | `oposicion` | Oposición | Enfrentó al régimen | Jugó ≥ 5 sets oficiales contra Spike | C | S, ID | ✔ | A0 | P | — | — | CR | T2 |
| 73 | `la_resistencia` | La resistencia | Lo hizo costumbre | Le ganó ≥ 3 sets oficiales a Spike, con cualquier seed | É | S, ID | ✔ | A0 | P | — | — | CR | T2 |
| 74 | `indulto` | Indulto | Revancha contra el régimen | Perdió con Spike y le ganó un set posterior en el mismo evento | É | S, ID | ✔ | A0 | P | Caso particular de `runback` | sí | CR | T2 |
| 75 | `decreto_supremo` | Por Decreto Supremo | Lo dijo la organización | Otorgado por la organización por una decisión o un evento especial, con motivo público | É | AD | ✔ | M | Lim | — | — | MC | T2 |
| 76 | `el_dictador_ha_hablado` | El Dictador ha Hablado | Reconocimiento comunitario | Otorgado por la organización como reconocimiento a un aporte a la comunidad, con motivo público | R | AD | ✔ | M | P | — | — | MC | T2 |
| 77 | `fiel_al_regimen` | Fiel al régimen | Nunca falta a un torneo de Spike | Jugó ≥ 10 torneos organizados por Spike | R | organizador del torneo | ✗ no se guarda quién organiza | AF | P | — | — | CR | T3 |

\* Pasan a T1 solo si se aprueban la decisión D2 (consentimiento e identidad) y su redacción.

### 2.8 Secretos y especiales

| # | ID | Nombre | Descripción | Condición exacta | Rar. | Datos | Disp. | Viab. | Tipo | Equivalente | Sec. | Origen | Prio. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 78 | `casi_kp` | Casi, kp | Subcampeón por una partida | Subcampeón de un principal de ≥ 16 que perdió su último set por una sola partida en la decisiva (1-2 o 2-3) | R | S, P | ✔ | A0 | P | — | — | MC | T1 |
| 79 | `pombero` | Pombero | Gana cuando todos duermen | Ganó un set completado entre las 00:00 y las 03:59 | R | S | ◐ `completed_at` puede ser la hora de carga del resultado | A0 | P | — | sí | PY-A | T2 |
| 80 | `nerfeado_por_la_trama` | Nerfeado por la trama | Era el seed 1… | Seed 1 de un principal de ≥ 16 que terminó fuera del top 8 | R | S, P | ✔ | A0 | P | — | h | MC | T2 |
| 81 | `no_pasar_pools` | No pasar pools | Un clásico de la escena | Quedó eliminado en la fase de pools de un evento con ≥ 2 fases | C | PL | ◐ | AF | P | Su contracara es `esta_vez_si` | h | MC | T3 |
| 82 | `los_johns` | Los Johns | Siempre hay una excusa | Perdió ≥ 10 sets en la partida decisiva (1-2 o 2-3) | R | S | ✔ | A0 | P | — | h | MC | T2 |
| 83 | `independencia` | Independencia | Campeón en fecha patria | Ganó un evento principal jugado el 14 o el 15 de mayo | É | P, T | ✔ | A0 | P | — | sí | CR | T2 |
| 84 | `coleccionista` | Coleccionista | Veinticinco logros | Tiene ≥ 25 logros permanentes, sin contar los de edición limitada | É | meta | ✔ | A0 | P | — | — | CR | T2 |

---

## 3. Recuento

| Categoría | Existentes | Nuevos | Total |
| --- | --- | --- | --- |
| Competitivos y brackets | 4 | 19 | 23 |
| Trayectoria y estadísticas | 9 | 17 | 26 |
| Rivalidades | 0 | 6 | 6 |
| Prode | 12 | 11 | 23 |
| Comunidad paraguaya | 0 | 9 | 9 |
| Multiverso de vBash | 0 | 7 | 7 |
| Régimen de Spike | 0 | 8 | 8 |
| Secretos y especiales | 0 | 7 | 7 |
| **Total** | **25** | **84** | **109** |

Por viabilidad (solo nuevos): A0 69 · AF 8 · M 4 · PD 3 (`nde_ru`, `terere_rupa`, `bvash`). Por tipo: 4 estados dinámicos (todos existentes), 4 de edición limitada y el resto permanentes.

Descartados en esta revisión, para no rellenar: 150 sets ganados, aniversario, pocket, ditto genérico, «el único con ese personaje», cara a cara con el n.º 1, fin de año en el setup, cebador oficial, voluntario, «Dictador vitalicio», pionero (se resuelve como «primero en conseguirlo» en la interfaz) y completista.

## 4. Primera tanda recomendada (T1: 28 + 2 condicionados)

Todos son **A0 con datos ✔**: no dependen de personajes reportados, pools, colores ni hora de reporte.

| Grupo | Logros |
| --- | --- |
| Brackets (13) | `mbarete`, `puerta_de_atras`, `ndeee`, `py_aguasu`, `primer_podio`, `primer_top8`, `desde_el_fondo`, `kane_o`, `runback`, `doble_corona`, `graduado`, `estreno`, `casi_kp` |
| Trayectoria (6) | `bautismo`, `de_la_casa`, `tuja`, `medio_centenar`, `aplanadora`, `fijo_top8` |
| Rivalidades (2) | `che_raa`, `exorcismo` |
| Prode (5) | `first_prode`, `almost_full`, `against_the_crowd`, `infaltable`, `double_duty` |
| Comunidad (2) | `siempre_en_la_ronda`, `ese_soy_yo` |
| Spike, si se aprueba D2 (2) | `dictador_caido`, `golpe_de_estado` |

Antes de publicarlos se miden contra la base real: cuántos jugadores tendrían cada uno. Si un logro «raro» lo tiene la mitad de la escena, se ajusta el umbral antes de lanzarlo (diseño §2.5).
