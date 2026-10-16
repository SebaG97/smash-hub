# Misión 02.1 — Auditoría de sets pendientes y BYE

> Consolidación autorizada (16/10/2026): se revisaron los cambios de ambas misiones, la cadena 0001 → 0002 → 0003 y los archivos nuevos. Validación repetida: 108 tests backend con PostgreSQL efímero aislado, 12 frontend, Ruff, ESLint, Prettier, build y TypeScript aprobados. Búsqueda de secretos sin incidencias; .env y temporales excluidos. Se prepara el commit `feat: implement startgg import and set classification` en `feature/mission-02-startgg-import`, seguido de la rama autorizada `feature/mission-03-player-statistics`. Los estados «sin commit» y «no iniciar Misión 03» del informe original describen el momento de su entrega; esta autorización posterior habilita la continuación. Sin push, producción ni despliegue.

Fecha: 16 de octubre de 2026. Rama: feature/mission-02-startgg-import. Auditoría y corrección ejecutadas exclusivamente en PostgreSQL local; sin producción, DigitalOcean, commit, push ni avance a Misión 03. Las conclusiones se basan en consultas autenticadas de solo lectura a start.gg, no en que los torneos figuren finalizados.

## Conclusión

Los 103 pendientes reportados en Misión 02 no eran encuentros entre oponentes: todos eran entradas vacías, state=1, sin entrants, ganador, scores, startedAt ni completedAt, con ambos slots prereqType=bye. Se reclasificaron como not_played/placeholder, sin convertirlos en completados ni inventar victorias. Los 83 BYE resueltos son otros IDs: tienen state=3, un entrant y ganador explícito; no hay intersección de IDs ni doble conteo del mismo BYE como pendiente.

La consulta normal también omitía dos Grand Finals Reset INVALID, recuperados con state:[5]. Se conservan como not_played/conditional_unused, con sus IDs externos originales. El reset de Burgame sí se disputó y se conserva played. Tras auditar los 309 sets, **no hay partidos verdaderamente pendientes** en estos tres torneos. Se mantienen 116 encuentros jugados, 5 DQ y 83 BYE; los resultados jugados no cambian.

## Conteos antes y después

Antes: la columna status legado mezclaba estado y resolución. El total no incluía los dos INVALID omitidos por la consulta por defecto.

| Torneo | Jugados | Pendientes | DQ | BYE | Total importado |
| --- | --- | --- | --- | --- | --- |
| gg-fest-x-eon | 48 | 27 | 0 | 27 | 102 |
| game-over-sep | 40 | 34 | 0 | 28 | 102 |
| super-smash-burgame-7 | 28 | 42 | 5 | 28 | 103 |

Después: categorías de resolución excluyentes; pendiente real requiere evidencia de un encuentro todavía sin resultado, no una posición de bracket sin oponentes.

| Torneo | Jugados | Pendientes reales | DQ | BYE resueltos | Placeholders | Reset no utilizado | Total auditado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gg-fest-x-eon | 48 | 0 | 0 | 27 | 27 | 1 | 103 |
| game-over-sep | 40 | 0 | 0 | 28 | 34 | 1 | 103 |
| super-smash-burgame-7 | 28 | 0 | 5 | 28 | 42 | 0 | 103 |

Los estados observados son completed=204 (116 played + 5 DQ + 83 BYE) y not_played=105 (103 placeholders + 2 resets condicionales). Solo los 116 played son candidatos a estadísticas de partidas jugadas/ranking; no se calculan estadísticas ni rankings en esta misión. Todos esos played tienen fecha final disponible en estos datos.

## Consultas comparadas

Se inspeccionaron id, state, winnerId, slots/entrants/scores, round, fullRoundText, startedAt, completedAt, hasPlaceholder y prerequisitos de slots. Se añadió phaseGroup.id/bracketType para validar dependencias de resets en doble eliminación. Los datos mínimos de cada set y su clasificación se conservan en [evidencia por set](mission-02-1-evidence.json); los snapshots completos previos quedan en .cache, excluidos de Git y sin token.

| Torneo | showByes=true normal | showByes=false normal | Excluidos por false | state:[5] explícito | Unión completa |
| --- | --- | --- | --- | --- | --- |
| gg-fest-x-eon | 102 | 48 | 54 | 1 | 103 |
| game-over-sep | 102 | 40 | 62 | 1 | 103 |
| super-smash-burgame-7 | 103 | 33 | 70 | 0 | 103 |

showByes=false elimina tanto BYE resueltos como entradas vacías con slots bye. En Burgame conserva los 5 DQ: sus 33 resultados son 28 jugados + 5 DQ. Por ello no sirve como sinónimo de «jugados». La consulta por defecto omite INVALID incluso con showByes=true. El cliente ahora descarga esa conexión y la de state:[5] por separado, valida ambas paginaciones y une por ID; si un mismo ID trae selecciones contradictorias aborta la importación.

sets.graphql es el documento versionado parametrizable mediante $showByes y $states. Referencias oficiales de campos/tipos revisadas: [Set](https://developer.start.gg/reference/set.doc.html), [SetSlot](https://developer.start.gg/reference/setslot.doc.html), [SetFilters](https://developer.start.gg/reference/setfilters.doc.html) y [PhaseGroup](https://developer.start.gg/reference/phasegroup.doc.html). La referencia oficial redirige al esquema publicado. No se presume introspección completa ni compatibilidad universal con otros juegos.

## Matrices de evidencia

«Antes» es el status legado importado en Misión 02; not_imported indica un INVALID omitido, no un set inventado. BYE slots cuenta los prerequisitos estructurados del slot, no victorias. DQ explícita requiere etiqueta DQ y score -1. El ganador indica presencia de winnerId original.

### gg-fest-x-eon

| state original | Antes | Estado observado | Resolución | Entrants reales | Ganador | Slots bye | DQ explícita | Cantidad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | pending | not_played | placeholder | 0 | no | 2 | no | 27 |
| 3 | bye | completed | bye | 1 | sí | 1 | no | 27 |
| 3 | completed | completed | played | 2 | sí | 0 | no | 48 |
| 5 | not_imported | not_played | conditional_unused | 0 | no | 0 | no | 1 |

### game-over-sep

| state original | Antes | Estado observado | Resolución | Entrants reales | Ganador | Slots bye | DQ explícita | Cantidad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | pending | not_played | placeholder | 0 | no | 2 | no | 34 |
| 3 | bye | completed | bye | 1 | sí | 1 | no | 28 |
| 3 | completed | completed | played | 2 | sí | 0 | no | 40 |
| 5 | not_imported | not_played | conditional_unused | 0 | no | 0 | no | 1 |

### super-smash-burgame-7

| state original | Antes | Estado observado | Resolución | Entrants reales | Ganador | Slots bye | DQ explícita | Cantidad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | pending | not_played | placeholder | 0 | no | 2 | no | 42 |
| 3 | bye | completed | bye | 1 | sí | 1 | no | 28 |
| 3 | completed | completed | played | 2 | sí | 0 | no | 28 |
| 3 | dq | completed | dq | 2 | sí | 0 | sí | 5 |

## Resets y placeholders identificados

- GG Fest: Grand Final 107729288 está resuelta; el reset 107729289 tiene state=5, cero oponentes y dependencias winner/loser del mismo set, en el mismo grupo DOUBLE_ELIMINATION. La fuente no registra inicio, ganador, score ni fecha final.
- Game Over: el mismo patrón vincula Grand Final 108258935 con reset 108258936.
- Burgame: Grand Final 108531447 y reset 108531448 tienen state=3, dos oponentes, ganador y scores válidos. El reset jugado no se reclasifica como no utilizado por su nombre.
- Ejemplos de entradas vacías: 107729290, 108258937 y 108531449. Su ronda es -1 / Losers Round 1, ambos prereqType=bye y ningún entrant. hasPlaceholder=false en estos casos: el booleano del proveedor no equivale a «hay dos oponentes reales».

La API numera Grand Final y su reset no utilizado con la misma round=3 en GG Fest y Game Over. Se descartó la suposición inicial de incremento obligatorio: se acepta ronda positiva igual o siguiente, además de todas las demás pruebas estructurales. El nombre solo nunca clasifica un reset como no utilizado. No se usa la finalización del torneo para promover pendientes.

## Cambio de modelo y persistencia

Nueva migración incremental 0003, sobre 0002 intacta; sin nuevas tablas. Agrega lifecycle_status, resolution, classification_reason, normalization_version, round_number y stats_eligible. El status anterior se conserva exclusivamente como formato legado de integridad para los triggers de 0001/0002. **No contar esa columna SQL como pendientes reales**: para consultas nuevas usar lifecycle_status y resolution.

El contrato público status devuelve lifecycle_status (pending, in_progress, completed, not_played, unknown). resolution distingue played, dq, bye, placeholder, conditional_unused, unresolved. Un set final sin puntuación suficiente conserva status=completed y ganador informado, resolution=unresolved y ambas elegibilidades false. No se inventa un 0 ni se llama pendiente solo porque falte score.

stats_eligible exige final played verificable, dos oponentes reales y scores coherentes; ranking_eligible añade fecha final. DQ, BYE, placeholders y resets no utilizados quedan excluidos de ambos. Los flags preparan futuros consumidores; no son cálculos de estadísticas/ranking.

La huella de un set incluye la clasificación versionada; un cambio de regla o evidencia de dependencia no queda bloqueado por un hash de fuente idéntico. Historial conserva selección anterior/nueva y ambas clasificaciones. Los lados se reutilizan cuando sus valores no cambian. Se comprobó la conservación de los 307 UUID de set originales, los 614 UUID/lados/ganadores/scores, campos originales de resultado y sus 307 snapshots previos en historial. Únicamente se agregaron los IDs 107729289 y 108258936, descubiertos en la API; no hay resultados reales modificados.

## Errores encontrados y corregidos

1. La migración falló inicialmente sobre datos existentes: cannot ALTER TABLE sets because it has pending trigger events. PostgreSQL revirtió toda la transacción; no hubo importaciones ni cambios parciales. Se corrigió validando los triggers diferidos con SET CONSTRAINTS ALL IMMEDIATE antes de agregar constraints y devolviendo el modo DEFERRED. La prueba nueva migra desde 0002 con resultados, verifica preservación y reimporta.
2. La primera regla estructural exigía round+1 para el reset; la evidencia real mostró round=3 tanto en final como reset. Por prudencia esos dos registros quedaron temporalmente como placeholder, nunca como jugados. Se corrigió la regla y se cubrieron numeraciones igual/siguiente con regresiones; dos reimportaciones correctivas cambiaron solo la clasificación de esos dos sets.
3. No hubo errores GraphQL, campos requeridos faltantes, duplicación de IDs ni conflictos de identidad durante la auditoría/reimportaciones. El documento original no solicitaba información suficiente del bracket ni INVALID explícitos; se amplió sin solicitar datos personales adicionales.

## Idempotencia y validación

Tras fijar la clasificación se tomó un manifiesto de las 18 tablas de dominio/referencia, con conteos, UUID y hashes lógicos, excluyendo import_jobs y timestamps operativos. Se reimportaron los tres torneos mediante la CLI. Cada ejecución final devolvió created=0, updated=0, conflictos=[]; el manifiesto final es idéntico. Los dos resets conservan los UUID creados al recuperarlos. Se guardan jobs independientes para cada intento y para las dos ejecuciones correctivas, sin ocultar el historial.

Pruebas: **108 backend con PostgreSQL efímero aislado**, sin omisiones; **12 frontend**, más lint, formato, build y TypeScript. Incluyen BYE resuelto, doble slot bye vacío, oponente ausente, DQ, placeholder explícito, pending real, in_progress, reset no utilizado por dependencias, reset jugado, nombre insuficiente, igual/siguiente ronda, final sin scores, fecha ausente, consulta explícita INVALID, rechazo de respuestas contradictorias y migración con datos existentes. El test real de preservación y el manifiesto de idempotencia complementan los fixtures, sin usar la base de desarrollo para tests destructivos.

La API se verificó con datos reales en las vistas matches/bracket/all, filtros status/resolution y paginación. view=matches es el default y excluye placeholders/resets no utilizados; BYE/DQ mantienen resolución propia y elegibilidad false. view=bracket permite auditar entradas sin enfrentamiento, view=all conserva el total. La web separa «Sets y resultados» y «Posiciones del bracket y rondas no disputadas»; muestra «Pase libre · Sin partido jugado», avance por BYE/DQ y «Reset condicional no utilizado», sin presentarlos como pendientes normales.

Las rutas web respondieron HTTP 200 y la regresión de componentes valida las etiquetas y filtros. No hubo navegador interactivo disponible en esta sesión para revisión visual; no se presenta HTTP como una inspección visual. Permanece revisión humana de diseño. Los avisos de deprecación de Starlette/AnyIO y cargador Vitest son conocidos y no fallos de suite.

## Estado operativo y límites

PostgreSQL local conserva los tres torneos para revisión y queda en revisión 0003. Los recursos efímeros de tests se limpian por separado. No se conectó a producción ni se tocó DigitalOcean/App Specs. Sin commit/push ni Misión 03. Los informes de Misión 02 conservan sus conteos como evidencia anterior y enlazan esta corrección.

La clasificación solo afirma lo que muestran slots, resultado y dependencias. Para otros torneos/juegos puede haber casos ambiguos: se conservan unresolved/unknown y no se habilitan estadísticas. No se infiere un BYE resuelto a partir de una única inscripción sin ganador ni se convierte un final sin scores en victoria jugada. La ausencia de torneos reales de dobles sigue cubierta por fixtures y no bloquea aprobación.

Comprobaciones públicas ejecutadas: 27 respuestas de API y 5 rutas web HTTP 200. Resultado de manifiesto: sin cambios.
