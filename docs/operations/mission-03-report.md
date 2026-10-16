# Informe de entrega — Misión 03

Fecha: 16 de octubre de 2026 (America/Asuncion). Estado: lista para revisión del responsable. Rama `feature/mission-03-player-statistics`. Implementación sin commit, push ni despliegue; no se inició Misión 04.

## Consolidación previa autorizada

Se permaneció inicialmente en `feature/mission-02-startgg-import`, se revisaron diff/archivos nuevos y se comprobó la cadena 0001 → 0002 → 0003. Auditoría de patrones de secretos, campos personales y coincidencias exactas de secretos privados contra entrega: sin incidencias. `.env`, cachés y temporales quedaron excluidos; `.env.example` solo tiene credenciales locales de ejemplo y token vacío.

Antes de consolidar aprobaron 108 tests backend con PostgreSQL aislado, 12 frontend, Ruff, ESLint, Prettier, TypeScript y build. Se actualizaron los informes históricos con la autorización posterior. Commit `d402e64`: `feat: implement startgg import and set classification`. Se creó la rama de Misión 03 desde ese commit y se verificó árbol limpio y migraciones 0001, 0002 y 0003 versionadas antes de empezar esta implementación. No se publicó ninguna rama ni se fusionó con main.

## Implementación

Módulo statistics con consultas SQL, política central de elegibilidad, servicio de agregación/perspectiva, contratos Pydantic y controladores HTTP separados. La consulta produce un set único con dos lados y rosters válidos; excluye DQ, BYE, placeholders, resets no usados, pendientes, ganador ausente, modalidades ambiguas y locks administrativos. Reutiliza clasificación 02.1. La excepción de lectura de finales sin score se ubica en el clasificador compartido y no modifica normalización, importación, identidades ni flags persistidos; ADR-010 explica la diferencia con el endpoint de auditoría.

Ámbito obligatorio de videojuego y modalidad singles/doubles; filtros por torneo, comunidad y período con timestamps timezone-aware. Métricas de sets y fechas se separan de inscripciones/placements. Sin denominador, win rate=null. Los resultados de dobles conservan el contexto de equipo separado de singles. H2H invierte perspectiva manteniendo los mismos sets y admite cero enfrentamientos. Paginación en SQL, límite 100, orden con UUID de desempate, tags en lote, sin N+1 y snapshot REPEATABLE READ por respuesta.

Frontend: perfil con sets, W/L, porcentaje, torneos, mejor placement, rivales y resultados recientes; carga/error/reintento/vacío/paginación. Filtros de juego/modalidad y período. Navegación desde rival a `/players/[id]/vs/[opponentId]`, identidades, marcador, porcentajes e historial. `/estadisticas` dirige a selección de jugadores. No se calculan métricas en frontend ni se agregan librerías, gráficos o animaciones.

## Endpoints y contratos

Cinco nuevos GET bajo `/api/v1/players/{id}`:

- `/statistics` — StatisticsView.
- `/matches` — MatchPage, cronológico descendente.
- `/opponents` — OpponentPage, frecuencia descendente.
- `/placements` — PlacementPage, solo finales confirmados.
- `/head-to-head/{opponent_id}` — HeadToHeadView, historial ascendente paginado.

Requieren game_id. Mode predeterminado singles, opcional doubles; tournament_id, community_id, date_from y date_to opcionales. Los listados/H2H aceptan page/page_size. Metadatos de filtros coherentes; 404 para jugador inexistente/no público, 422 para UUID/filtros inválidos o autocomparación, 200 para ausencia de encuentros. PlayerDetail añade scopes públicos de juego/modalidad. Endpoints anteriores conservados y cubiertos por la suite completa. Contratos detallados y snapshot OpenAPI actualizados.

## Migraciones y rendimiento

No hay migración 0004 ni tablas precalculadas. Migraciones 0001–0003 idénticas al commit base; ningún modelo SQL se modificó. Se revisaron índices existentes de sets/evento, lados/set/entrant, rosters/participante y filtros evento/juego/torneo. EXPLAIN ANALYZE BUFFERS en la base local: universo 5.193 ms, recientes 7.242 ms y rivales 7.269 ms, una medición sobre 309 registros importados; no son garantías de latencia para otro volumen/host. Los planes completos se guardan en mission-03-evidence.json. No se observó necesidad de nuevos índices al volumen actual. Un futuro motor de rating puede reutilizar el universo sin acoplarse a respuestas HTTP.

## Validación final

| Control | Resultado |
| --- | --- |
| Backend, PostgreSQL 17.7 efímero aislado | **155 passed**, sin omisiones |
| Frontend Vitest | **20 passed**, tres archivos |
| Total de tests aprobados | **175** |
| Ruff lint / formato backend | Aprobados |
| ESLint / Prettier frontend | Aprobados |
| Next.js build / TypeScript | Aprobados |
| Snapshot OpenAPI | Aprobado en suite |
| git diff --check y migraciones sin cambios | Aprobados |
| Auditoría de secretos de entrega | Sin incidencias |
| Cinco endpoints nuevos con datos locales reales | HTTP 200, más reverso H2H, scopes y período |

Los 47 tests backend nuevos cubren W/L, homónimos y tags cambiantes, datos ausentes, no sets/null, exclusiones administrativas, excepción sin score con once casos de evidencia, fechas y límites timezone-aware, ámbito juego/torneo/comunidad, dobles y compañeros, placements provisionales, registro sin actividad, simetría/ausencia/autocomparación H2H, paginación/desempate, reimportación, corrección y recálculo, publicación, URL de origen segura, número constante de consultas, contratos y guardas de CLI contra producción/remotos/otra base. Ocho nuevos tests frontend cubren perfil, comparación, vacío/null, filtros, dobles, fechas inválidas, paginación, errores/reintento y autocomparación. Ningún test requiere start.gg.

Los intentos iniciales dentro del sandbox de Windows encontraron restricciones de procesos (EPERM) y acceso al motor Docker; se repitieron con el acceso local necesario y aprobaron íntegramente. Persisten avisos de deprecación de Starlette/AnyIO y configuración futura de Vitest, sin fallos. La comprobación frontend incluye componentes y build; no se afirma una inspección visual interactiva de navegador. No se ejecutó CI remoto porque no hay push. Los recursos de compose.test se limpiaron por separado, conservando el volumen de desarrollo.

## Validación con torneos reales

CLI `app.cli.validate_statistics`, sin solicitudes al proveedor, exclusivamente PostgreSQL local en READ ONLY; todas las estadísticas se reconciliaron contra los sets de cada jugador y torneo.

| Torneo | Sets elegibles | Placeholders | BYE | DQ | Reset no usado |
| --- | --- | --- | --- | --- | --- |
| GG Fest x EON | 48 | 27 | 27 | 0 | 1 |
| Game Over SEP | 40 | 34 | 28 | 0 | 1 |
| Super Smash Burgame 7 | 28 | 42 | 28 | 5 | 0 |
| **Total** | **116** | **103** | **83** | **5** | **2** |

**116 UUID de set distintos, 116 victorias y 116 derrotas** en singles. Las categorías administrativas no aportan W/L. 38 jugadores únicos, 18 en varios torneos y 7 en los tres. Las cifras coinciden con la referencia después de verificarlas; no se agregaron constantes de conteos a la lógica. Sin diferencias sin explicar.

Ejemplo real: **Wesker**, UUID `d652a1b2-75bc-475e-9cd8-29133ba07277`, Ultimate singles: 19 sets, 16 victorias, 3 derrotas, 84.21 %, tres torneos disputados y tres con inscripción, mejor placement final 1, 11 rivales distintos. Primer set 2026-09-13T20:35:08Z; último 2026-10-04T03:11:52Z. Estos son instantes UTC devueltos por la API; la web muestra fechas de Paraguay.

Ejemplo real H2H: **Wesker vs. Zephyr**, UUID del rival `5768be73-ba45-40cc-b544-29512686a441`: siete enfrentamientos, 5–2, 71.43 % / 28.57 %. El reverso conserva los siete sets e invierte W/L. Game UUID `c9af89c3-9dd7-4f5d-978a-c79f7e650609`. Respuestas completas e historial real en [evidencia](mission-03-evidence.json).

## Problemas encontrados, riesgos y pendientes

- La base anterior no estaba confirmada: se resolvió mediante el commit autorizado, antes de crear esta rama.
- 02.1 excluía finales sin scores; 03 exige contarlos con ganador válido. Se añadió una excepción central de lectura y motivo explícito, con pruebas; no se altera la importación. La auditoría del evento conserva su flag histórico, diferencia documentada.
- El componente Collection enviaba q incluso sin búsqueda; los filtros estrictos nuevos lo rechazan. Ahora solo envía q cuando se habilita búsqueda, conservando búsqueda de jugadores/torneos.
- El generador del diccionario tenía orden variable de referencias FK: ahora las ordena para salida determinista, sin cambio de esquema.
- País/región siguen pendientes por calidad de datos. No se infiere residencia desde comunidad.
- Fechas desconocidas no se inventan. Inscripciones/placements se filtran por inicio de torneo; sets por finalización, distinción documentada.
- El esquema no distingue revisión administrativa pendiente/aprobada; todos los locks de set/mapping start.gg excluyen conservadoramente hasta resolución y desbloqueo.
- Dobles devuelve resultados de equipos por ámbito; no representa rating individual. Las evidencias reales son singles; dobles se valida con fixtures.
- Rendimiento observado es local y de bajo volumen; reconsiderar índices o representación de la excepción si cambia la escala. No hay precálculo ni proveedor en HTTP.
- Pendiente revisión humana del responsable y visual de la interfaz. No se autoriza commit de Misión 03, push, despliegue ni Misión 04.

## Documentación y estado de Git

Actualizados README, arquitectura general y módulos, contratos/OpenAPI, seguridad y operaciones locales. Creados docs/statistics.md, ADR-010, CLI reproducible, evidencia y este informe. El diccionario solo cambia en el orden determinista de referencias; el esquema no cambia. DigitalOcean y sus configuraciones no se modificaron en Misión 03 porque no fue necesario.

HEAD `d402e64`; rama `feature/mission-03-player-statistics`; cambios de Misión 03 sin staging ni commit. Árbol limpio comprobado al crear la rama; ahora contiene exclusivamente la implementación pendiente de revisión. Sin reset --hard, descarte, force push, merge a main, push, despliegue ni conexión/modificación de producción.

Archivos modificados o nuevos respecto del commit base:

- `README.md`
- `apps/api/app/cli/validate_statistics.py`
- `apps/api/app/competitions/router.py`
- `apps/api/app/health/router.py`
- `apps/api/app/integrations/startgg/classification.py`
- `apps/api/app/main.py`
- `apps/api/app/statistics/__init__.py`
- `apps/api/app/statistics/contracts.py`
- `apps/api/app/statistics/policy.py`
- `apps/api/app/statistics/repository.py`
- `apps/api/app/statistics/router.py`
- `apps/api/app/statistics/service.py`
- `apps/api/tests/test_statistics.py`
- `apps/web/src/app/[module]/page.tsx`
- `apps/web/src/app/estadisticas/page.tsx`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/players/[id]/vs/[opponentId]/page.tsx`
- `apps/web/src/components/competition-browser.tsx`
- `apps/web/src/components/player-statistics.tsx`
- `apps/web/src/lib/api.ts`
- `apps/web/tests/statistics.test.tsx`
- `docs/adr/ADR-010.md`
- `docs/api/contracts.md`
- `docs/api/openapi.json`
- `docs/architecture/modules.md`
- `docs/architecture/overview.md`
- `docs/database/schema.md`
- `docs/operations/local-development.md`
- `docs/operations/migrations.md`
- `docs/operations/mission-03-evidence.json`
- `docs/operations/mission-03-report.md`
- `docs/security/security.md`
- `docs/statistics.md`
- `scripts/generate_schema_docs.py`
