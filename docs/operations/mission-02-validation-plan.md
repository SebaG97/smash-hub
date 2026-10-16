# Plan y evidencia de validación — Misión 02

> Actualización Misión 02.1: este documento conserva los conteos de la validación anterior a 0003. La auditoría posterior identifica los 103 «pendientes» como placeholders y recupera dos resets INVALID antes omitidos; los resultados jugados no cambian. Consultar el [informe Misión 02.1](mission-02-1-report.md) para la clasificación vigente, matrices y pruebas.


Alcance corregido por el responsable el 16/10/2026. Los siguientes torneos están confirmados como exclusivamente singles. No se organizaron torneos de dobles en la comunidad durante 2026, según la confirmación del responsable. Esta información define los casos de prueba; no se usa para sobrescribir modalidad ni resultados del proveedor.

| Caso real autorizado | Modalidad esperada | Primera importación | Comparación con start.gg | Reimportación |
| --- | --- | --- | --- | --- |
| gg-fest-x-eon | Singles | Ejecutada, completed | Sin diferencias | Ejecutada, sin duplicados |
| game-over-sep | Singles | Ejecutada, completed | Sin diferencias | Ejecutada, sin duplicados |
| super-smash-burgame-7 | Singles | Ejecutada, completed | Sin diferencias | Ejecutada, sin duplicados |

El token se verificó con el preview real de gg-fest-x-eon, sin mostrar su contenido. Se hicieron seis ejecuciones persistentes locales (importación y reimportación de cada torneo), sin alterar datos en start.gg. Conteos y limitaciones observados se detallan abajo; no se inventaron resultados.

## Procedimiento de validación real de singles

Usar exclusivamente PostgreSQL local, migración 0002 y bootstrap; conservar los jobs de cada ejecución. Configurar STARTGG_API_TOKEN en el entorno privado, nunca en comandos, Git ni chat. No modificar registros del proveedor.

1. Ejecutar preview de cada slug y verificar que los eventos esperados correspondan al juego y modalidad estructurados. Si el proveedor contradice la expectativa, registrar discrepancia y revisar; no forzar team_size por nombre o por esta lista.
2. Importar los tres torneos con la CLI. Guardar resumen, UUID interno, job y fecha de observación. No cargar fixtures con estos slugs ni nombres de personas reales.
3. Comparar por cada evento con start.gg: total de entrants (diferenciado de participantes), integrantes, seeds disponibles, placements finales y lista de sets. Comparar ronda, oponentes, ganador, scores nullable y estado pendiente/DQ/BYE/incompleto. Registrar diferencias concretas; no rellenar datos ausentes.
4. Para cada Player.id compartido entre los tres snapshots, comprobar un solo external_identities y players.id; cada participación debe conservar su tag_snapshot y torneo, sin perder resultados. Comparar también homónimos: Player.id distintos no se fusionan por tag. Las identidades sin Player.id permanecen provisionales y separadas por inscripción. No publicar IDs externos en la API pública.
5. Reimportar cada torneo. Para fuente sin cambios: mismos UUID y filas de dominio, created=updated=0, nuevos jobs de auditoría y tiempos de sincronización actualizados. Si start.gg cambió entre lecturas, registrar el cambio y verificar historia/prioridad; no describirlo como fallo de idempotencia ni ocultar la corrección.
6. Consultar API y frontend contra esa base local. Adjuntar evidencia de los conteos y resultados realmente observados, incluyendo errores o conflictos sin secretos.

```sh
python -m app.cli.import_tournament --slug gg-fest-x-eon --dry-run
python -m app.cli.import_tournament --slug game-over-sep --dry-run
python -m app.cli.import_tournament --slug super-smash-burgame-7 --dry-run
python -m app.cli.import_tournament --slug gg-fest-x-eon
python -m app.cli.import_tournament --slug game-over-sep
python -m app.cli.import_tournament --slug super-smash-burgame-7
# Repetir las últimas tres importaciones para comprobar idempotencia.
```

Estos comandos corresponden al procedimiento utilizado; la evidencia real agregada se registra a continuación. El entorno nativo requiere dependencias y configuración de API; alternativa Compose en el runbook.

## Validación automatizada con datos sintéticos

| Aspecto | Evidencia |
| --- | --- |
| Singles/dobles | Fixture startgg.json con eventos de tamaño 1 y 2; miembros individuales y FKs verificadas en PostgreSQL |
| Identidad entre torneos | Tres torneos sintéticos, dos identidades globales compartidas, tags diferentes, importación fuera de orden y reimportación sin duplicados |
| Persona en varios eventos | Un participante integra singles y dobles del mismo torneo conservando un jugador |
| Homónimos y provisionales | Mismo tag con IDs distintos; participante sin Player.id separado |
| Resultados | Completado, pendiente con scores parciales no publicados como final, DQ, BYE, score/fecha ausentes y casos ambiguos |
| Correcciones | Historial de resultado, revisiones antiguas rechazadas, locks manuales, conflictos de identidad, tags históricos preservados |
| Integración HTTP | Documentos GraphQL reales con MockTransport, CLI preview/import, paginación múltiple, errores, rate limiting, backoff y redirects rechazados |
| Atomicidad y concurrencia | Falla durante persistencia, rollback sin publicación parcial, repetición segura y locks PostgreSQL |
| Migraciones | 0001 intacta; comparación metadata, ida/vuelta, conservación de datos compatibles y rechazo de rollback con datos incompatibles |
| Interfaz | Torneos, detalle de torneo/evento/jugador, búsqueda, miembros, placements, carga, error, reintento, vacío y 404 |

Los fixtures no representan resultados competitivos reales ni se cargan automáticamente en desarrollo. La ausencia de torneos reales de dobles **no bloquea la aprobación de Misión 02**. Su compatibilidad se evalúa mediante modelo, constraints, fixtures sintéticos y tests automatizados. La validación real de los tres casos singles, identidad compartida, comparación con proveedor e idempotencia se ejecutó el 16/10/2026. La inspección visual interactiva queda para revisión humana por ausencia de navegador disponible.

## Evidencia real obtenida

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

Los fixtures de dobles y casos sintéticos permanecen claramente separados de esta evidencia real. Pruebas repetidas tras la importación: 83 backend con PostgreSQL efímero y 11 frontend; lint, formato, build y tipos aprobados. No se usó la base de desarrollo para la suite destructiva. DigitalOcean y producción no se tocaron; no se hizo commit.
