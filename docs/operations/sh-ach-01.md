# SH-ACH-01 — Sistema de logros: implementación y publicación

Fecha: 12/11/2026. Publicación autorizada el 12/11/2026; su estado real está en la [sección 8](#8-publicación-resultados-reales). Diseño: [docs/logros/](../logros/README.md). Decisión: [ADR-023](../adr/ADR-023.md).

## 1. Qué se implementó

| Bloque | Contenido |
| --- | --- |
| Catálogo único | `app/achievements/catalog.py`: los 109 logros, incluidos los 25 existentes con sus identificadores, nombres y condiciones. Se expone en `GET /api/v1/achievements/catalog`. La web ya no repite la lista del Prode (`ACHIEVEMENTS`) ni los colores de emblemas (`BADGE_TONE`). |
| Persistencia | Migración `0024`, aditiva: `player_achievements`, `achievement_stats`, `achievement_subjects`, `achievement_runs`, `achievement_audit` y `user_showcase`. Además, columnas nuevas en `prode_achievements` y un índice único parcial para los logros acumulados. |
| Prode | `settle`, los logros acumulados y la anulación concilian en lugar de borrar y recrear. `created_at` es el primer reconocimiento y no cambia; lo que deja de cumplirse se revoca y, si vuelve a cumplirse, se reactiva. Hay 10 logros nuevos. Los puntajes y las reglas de puntuación no cambian. |
| Motor de jugador | `app/achievements/rules.py` (reglas puras) y `service.py` (contexto, conciliación idempotente, estadísticas). Corre en segundo plano (`runner.py`) o cuando lo pide un administrador; nunca al abrir una página. |
| API | Pública: catálogo, detalle, perfil de jugador y de cuenta. Del dueño: sus logros, la vitrina y la visibilidad. De organizadores: estado, recálculo, personas de referencia, y otorgar o revocar logros manuales. |
| Web | `/logros` (filtros, colecciones, progreso, secretos), `/logros/[id]`, vitrina y «Ahora mismo» en la ficha del jugador, vitrina en el perfil del Prode, «Logros y vitrina» en Mi cuenta y la sección «Logros» en `/admin`. |

### Correcciones de reglas aprobadas

- **Por la puerta de atrás:** el campeón tiene que llegar a la gran final desde la **final de losers**, con rondas negativas de start.gg (`sets.round_number`), y haber perdido un set en el evento. Si faltan las rondas, no se otorga.
- **Golpe de Estado:** el set ganado a Spike tiene que ser el **último set de Spike en ese evento**, con su posición final registrada, seeds del mismo evento y seeding fiable.
- **Casi, kp:** el subcampeón tiene que perder su **último set (la gran final decisiva, o el reset si hubo)** contra el campeón por una sola partida.
- **Niveles:** «Campeón» ya no desaparece al llegar a «Coleccionista de trofeos». Esto también se ve en `/insights/players/{id}`, donde ahora aparecen los dos. Ningún logro permanente se pierde por alcanzar otro umbral.
- **Humor:** los logros de humor son públicos por defecto y el dueño puede ocultar cualquiera, de a uno.

## 2. Logros activos

**Automáticos desde el primer recálculo (52 nuevos más los 21 existentes permanentes o del Prode).**

- **Jugador (42):** `mbarete`, `puerta_de_atras`, `reset_y_corona`, `purete`, `ndeee`, `py_aguasu`, `primer_podio`, `primer_top8`, `desde_el_fondo`, `barrida`, `reverse_3_0`, `kane_o`, `runback`, `doble_corona`, `graduado`, `estreno`, `bautismo`, `de_la_casa`, `tuja`, `cincuenta_brackets`, `medio_centenar`, `trescientos`, `aplanadora`, `nunca_muerto`, `fijo_top8`, `tricampeon_mes`, `constancia`, `volvio`, `conoce_a_todos`, `jopara`, `che_raa`, `clasico`, `exorcismo`, `en_bici_hasta_cde`, `siempre_en_la_ronda`, `ese_soy_yo`, `la_mufa_no_funciona`, `casi_kp`, `nerfeado_por_la_trama`, `los_johns`, `independencia`, `coleccionista`.
- **Prode (10, al liquidar):** `first_prode`, `almost_full`, `against_the_crowd`, `paje`, `infaltable`, `double_duty`, `early_bird`, `last_minute`, `jinx`, `podium_streak`.
- **Existentes:** los 9 emblemas permanentes ahora se guardan con historial. Los 4 estados (`lider`, `nuevo`, `especialista`, `camaleon`) se siguen calculando al vuelo. Los 12 del Prode no cambian sus condiciones.

Incluye los 28 de la primera tanda (T1) y todos los T2 con datos fiables.

**Preparados pero inactivos hasta confirmar identidad y consentimiento (9):** `dictador_caido`, `golpe_de_estado`, `oposicion`, `la_resistencia`, `indulto` (Spike); `todos_somos_vbash`, `que_vbash_sos`, `vbash_contra_vbash`, `multiverso_vbash` (vBash).

**Manuales (4):** `anfitrion`, `decreto_supremo` y `el_dictador_ha_hablado`. Los dos últimos solo funcionan con la colección de Spike activa. `el_verdadero_vbash` funciona con la de vBash activa.

**Pendientes, registrados y nunca otorgados (19):**

| Logro | Motivo |
| --- | --- |
| `bicampeon` | No existe la serie de cada torneo. |
| `dueno_del_pool`, `esta_vez_si`, `el_seeding_nos_odia`, `no_pasar_pools` | Los pools solo existen desde SH-SYNC-01 y no están unidos a los sets importados. |
| `fue_numero_uno`, `top10_ranking`, `escalador`, `destronar` | Falta un historial verificable de publicaciones del ranking. |
| `nde_ru`, `bvash` | Validación de la comunidad. |
| `season_champion` | No hay temporadas del Prode. |
| `nande` | Los prefijos de equipo no tienen historial fiable por torneo. |
| `terere_rupa` | start.gg no informa la hora real de inscripción. |
| `estuve_ahi` | Falta marcar las ediciones especiales. |
| `fundador` | Es un logro de cuenta; falta un almacén por cuenta. |
| `vbash_rojo` | start.gg no informa el color usado en cada partida. |
| `fiel_al_regimen` | No se guarda quién organiza cada torneo. |
| `pombero` | Desactivado temporalmente en la publicación: la hora de start.gg puede ser la de carga del resultado. La regla queda escrita y probada. |

## 3. Migración `0024`

`apps/api/migrations/versions/0024_achievements.py`, sobre `0023`.

- **Crea tablas:** `player_achievements` (único por `player_id, achievement_id, occurrence`), `achievement_stats`, `achievement_subjects`, `achievement_runs`, `achievement_audit` y `user_showcase`.
- **Agrega a `prode_achievements`:** `event_at` y `evidence` (nulos), `status` (`'active'` por defecto), `revoked_at` (nulo) y `hidden` (`false` por defecto). Las filas existentes quedan activas y visibles, igual que hoy.
- **No modifica datos.** Antes de crear `uq_prode_achievements_lifetime (user_id, kind) WHERE contest_id IS NULL`, cuenta los logros acumulados duplicados (mismo usuario y `kind`, `contest_id` nulo). Si hay alguno, **aborta con un error y no aplica nada**: no borra registros del Prode. Probado en `test_migration_0024_stops_on_duplicated_lifetime_achievements`.
- **Verificado en PostgreSQL efímero:** upgrade a head, comparación de metadatos sin diferencias (`test_schema_matches_metadata`) y roundtrip base ↔ head (`test_migration_roundtrip`).
- **El downgrade** borra las tablas nuevas y las columnas agregadas. Si se usara, los logros del Prode revocados volverían a mostrarse: antes de bajar, borrar las filas con `status = 'revoked'`.

## 4. Pruebas ejecutadas

| Suite | Resultado |
| --- | --- |
| API completa (PostgreSQL 17 efímero, `TEST_DATABASE_URL`) | **355 aprobadas.** Nuevas: `tests/test_achievements.py` (12) y 2 en `tests/test_prode.py`. |
| Web (Vitest) | **137 aprobadas**, incluidas 6 nuevas en `tests/achievements.test.tsx`. |
| `ruff check`, `ruff format --check` | Sin observaciones. |
| `tsc --noEmit`, `eslint --max-warnings 0` | Sin errores. |
| Prettier | Los archivos nuevos y modificados están formateados. Hay 48 avisos previos en el repo por finales de línea de Windows, ajenos a este cambio. |
| `next build` | Compila; `/logros` y `/logros/[id]` están incluidas. |
| Contrato OpenAPI | `docs/api/openapi.json` regenerado: solo agrega rutas `/achievements`; las existentes no cambian. |

**Qué cubren las pruebas:**
- **Catálogo:** 109 logros, los 25 existentes intactos y ningún pendiente activo.
- **Reglas:** losers real, reset, final decisiva, eliminación real de Spike, seeds no fiables y conservación de niveles.
- **Persistencia:** idempotencia (dos corridas sin duplicados ni fechas nuevas), revocación al despublicar un torneo y reactivación con la fecha original.
- **Colecciones restringidas:** solo superadmin, sin consentimiento no se activan, y el ID de start.gg tiene que existir.
- **Logros manuales:** motivo obligatorio, sin duplicados, revocación, y el recálculo no los toca.
- **Vitrina:** solo logros propios, máximo 3, sin repetir, con el encabezado de la web; la ocultación respeta la vitrina.
- **Secretos:** se revelan solo a su dueño.
- **Compatibilidad:** `badges` mantiene su forma.
- **Datos importados:** evaluación sobre el torneo real del fixture de start.gg.
- **Prode:** una segunda liquidación con los mismos resultados deja **las mismas filas con el mismo `created_at`** y no toca pronósticos ni puntajes. Una corrección revoca sin borrar, volver a los resultados restaura con la fecha original, y la anulación revoca todo, también los acumulados.

**Rendimiento:** las reglas sobre 9.000 sets, 600 jugadores y 150 torneos sintéticos tardan 2,7 s, en segundo plano.

## 5. Compatibilidad con producción

- **Prode activo (Center Stage):** no se ejecutó ninguna liquidación ni anulación sobre datos reales.
  - Con este código, liquidar Center Stage funciona igual para puntajes y ranking.
  - La diferencia es que los logros se concilian, y que se suman los 10 nuevos que correspondan.
  - Si se liquida **antes** de desplegar, el código actual crea los logros como siempre. Al desplegar, `0024` los conserva con su fecha, y una liquidación posterior los concilia sin recrearlos.
- **APIs existentes:** `/prode/*` y `/insights/*` mantienen sus formas. Hay tres cambios visibles:
  1. `badges` puede incluir «Campeón» junto a «Coleccionista de trofeos».
  2. Los logros del Prode ocultos por su dueño o revocados ya no se listan.
  3. Anular un Prode liquidado revoca sus logros (antes quedaban visibles).
- **Volver al código anterior** sin bajar la migración es seguro: las columnas nuevas tienen valores por defecto y el código anterior no las usa.
- **Evaluación automática apagada por defecto** (`ACHIEVEMENTS_AUTO=false`). Hasta encenderla, solo hay recálculos manuales desde `/admin`.

## 6. Problemas conocidos y riesgos

1. **No hubo prueba visual en un navegador real.** Están verificados los componentes (Vitest), los tipos y el build. Conviene revisar `/logros`, una ficha y Mi cuenta en un celular antes de anunciar.
2. **Calibración pendiente.** Las rarezas de diseño no se compararon con datos reales. Revisarlas con la primera corrida: si un épico lo tiene más del 20 % de su universo, ajustar el umbral.
3. **Primer reconocimiento retroactivo.** La primera corrida marca todo como «reconocido retroactivamente» (`backfilled`). Algunos logros no tienen fecha real del hecho (`mes`, `tricampeon_mes`, `todos_somos_vbash`, `coleccionista`), así que no participan de «primero en conseguirlo».
4. **«Pombero»** usa `completed_at` de start.gg, que puede ser la hora en que se cargó el resultado y no la del set. Por eso quedó desactivado (pendiente).
5. **Importaciones desde la CLI** (otro proceso) no avisan al proceso de la API. Las detecta la corrida periódica (cada 6 h por defecto) o un recálculo manual. Las importaciones desde la web sí avisan.
6. **Un logro por jugador:** se guarda el primer desbloqueo (`occurrence = ''`); las repeticiones solo se cuentan en la evidencia de algunos.
7. **Corregir o despublicar un torneo** revoca los logros que dependían de él (se ven como revocados en la base, no en la web).
8. **La imagen OG del jugador** sigue usando los emblemas anteriores.
9. **Spike y vBash:** falta confirmar su consentimiento y su ID de jugador de start.gg.

## 7. Pasos exactos para publicar (requieren autorización)

0. **Dependencias.** La rama parte de `b50e19f` (SH-FIX-01), que incluye SH-SYNC-01. Si producción no tiene esos cambios, este despliegue también los publica: seguir antes sus guías ([startgg-sync.md](startgg-sync.md), [sh-fix-01.md](sh-fix-01.md)). `STARTGG_SYNC_ENABLED` no cambia.
1. **Revisión y push**, con autorización: integrar `sh-ach-01` en `main` y hacer push. No hay `deploy_on_push`.
2. **Respaldo:** confirmar el backup diario del día y la recuperación a un punto en el tiempo.
3. **Revisión actual de la base:** confirmar la revisión aplicada (`0023` si SH-FIX-01 ya se publicó).
4. **Spec de la app** (en una sola edición desde el panel):
   - job `migrate`: `APPROVED_MIGRATION` → `0024`. Aplica también `0020`–`0023` si faltan.
   - `api`: agregar `ACHIEVEMENTS_AUTO=false`.
5. **Desplegar.** Verificar:
   - `GET /api/v1/health/ready` → 200.
   - `GET /api/v1/achievements/catalog` → 200, con 109 logros.
   - `/logros` y `/logros/oracle` → 200.
   - `/prode` y la previa de Center Stage siguen funcionando.
   - `GET /api/v1/prode/tournaments/center-stage-2026-1` devuelve el mismo `locks_at` y la misma cantidad de participantes que antes.
6. **Primer cálculo:** en `/admin` → Logros → «Recalcular ahora». Esperar a que la corrida figure `completed` y revisar los conteos (nuevos, revocados = 0). Abrir 3 o 4 fichas de jugadores conocidos y comparar con lo esperado.
7. **Calibración:** revisar en `/logros` las etiquetas de rareza. Si hace falta ajustar umbrales, se cambia el código y se vuelve a desplegar antes de anunciar.
8. **Encender la evaluación automática:** `ACHIEVEMENTS_AUTO=true` en `api` (redeploy). Desde ahí se evalúa después de cada importación desde la web, publicación de ranking, liquidación o vinculación, y cada 6 h.
9. **Spike y vBash, solo con consentimiento:** un superadmin, en `/admin` → Logros → Personas de referencia, carga el ID de jugador de start.gg, marca el consentimiento y activa la colección. Después, «Recalcular ahora».
10. **Logros manuales:** desde `/admin` → Logros manuales, con motivo público.

## 8. Publicación: resultados reales

Autorizada el 12/11/2026. App `smash-hub-app` (`https://smash-hub-app-d4eh4.ondigitalocean.app`), base `segir-db-1` (PostgreSQL 18).

### 8.1 Verificaciones previas (12/11/2026, ~19:00 UTC)

| Verificación | Resultado |
| --- | --- |
| Rama vs `main` | `origin/main` = `b50e19f` (SH-FIX-01, ya incluye SH-SYNC-01) es ancestro de `sh-ach-01`: la integración es un avance rápido y no se pierde ningún cambio de `main`. |
| Código en producción | El contrato `GET /api/openapi.json` de producción es **idéntico** al de `b50e19f`: producción corre SH-FIX-01. Existen `/api/v1/sync` (401 sin sesión) y `/prode/contests/{id}/locks-at`. `/api/v1/achievements/catalog` responde 404, como se espera antes de publicar. |
| Revisión de la base | **No se pudo confirmar.** El token de `doctl` (contexto `smashhub`) no tiene permisos sobre Apps (403: ni spec, ni logs del job `migrate`, ni despliegues) y DigitalOcean no entrega las credenciales de la base. Por comportamiento, `/insights/calendar` y la previa de Center Stage responden 200, pero las lecturas de la copia local caen a start.gg si la base falla (ADR-022), así que eso no prueba que `0023` esté aplicada. |
| Respaldo | Backups diarios automáticos disponibles; el último es del **12/11/2026 00:43 UTC** (~99 MB). Lo posterior, incluidos los pronósticos del Prode de hoy, solo se recupera con la restauración a un punto en el tiempo del clúster. No se pudo hacer `pg_dump` (sin credenciales). |
| Prode de Center Stage (línea base) | `bc47671b…`: `open`, **8 participantes**, 91 candidatos, `locks_at = 2026-11-14T19:00:00+00:00`, sin liquidar. Es el único Prode y la tabla general está vacía: no hay liquidaciones, así que no debería haber filas en `prode_achievements`. |
| Observación ajena a SH-ACH-01 | El cierre de Center Stage sigue a las **19:00 UTC (16:00 en Asunción)**: el paso 5 de [SH-FIX-01](sh-fix-01.md) (14:00 en Asunción, `17:00 UTC`) no figura aplicado. No se tocó. |

### 8.2 Cambios previos a publicar (pedidos en la autorización)

- **`pombero` desactivado:** pasa a pendiente en el catálogo (sigue visible como «Próximamente») y no se otorga.
- **`0024` no borra registros del Prode.** Si hubiera logros acumulados duplicados, la migración **aborta** con `RuntimeError` antes de crear el índice: el job `migrate` falla, el despliegue no avanza y la base queda en `0023`. Reemplaza la deduplicación anterior.

### 8.3 Integración y push

- `sh-ach-01` se integró en `main` por avance rápido y se hizo push: `origin/main` pasó de `b50e19f` a **`ab6c22a`**. Commits: `0538ba1` (backend), `8cd423f` (web), `4b07e55` (docs) y `ab6c22a` (pombero y protección de `0024`).
- Pruebas antes del push: **API 355 aprobadas** (PostgreSQL 17 efímero), web 137 aprobadas, `ruff`, `tsc`, `eslint` y `next build` sin errores. La CI de GitHub no se pudo consultar desde esta máquina (no hay `gh`).
- El push **no desplegó**: después de hacerlo, `/api/v1/achievements/catalog` en producción sigue respondiendo 404 (no hay `deploy_on_push`).

### 8.4 Publicación detenida: falta acceso a App Platform

Los pasos 4 a 9 de la sección 7 **no se ejecutaron**. El token de `doctl` responde 403 en Apps, así que desde aquí no se puede:
- editar el spec (`APPROVED_MIGRATION`, `ACHIEVEMENTS_AUTO`);
- desplegar ni ver qué commit corre;
- leer los logs del job `migrate`.

Tampoco hay una sesión de administrador para usar «Recalcular ahora», ni un navegador para la revisión visual. Además, la revisión de la base y un respaldo posterior a las 00:43 UTC siguen sin confirmar (8.1).

Para continuar, el propietario (desde el panel, como en el despliegue del Prode) o un token con permisos de Apps:
1. En el panel, abrir el último despliegue → job `migrate` → logs: confirmar la revisión aplicada (se espera `0023`).
2. Confirmar el respaldo o la restauración a un punto en el tiempo del clúster `segir-db-1`.
3. Editar el spec en una sola edición: job `migrate` `APPROVED_MIGRATION=0024`; `api` agregar `ACHIEVEMENTS_AUTO=false`. Desplegar `ab6c22a`.
4. Avisar para verificar desde aquí (salud, catálogo de 109, `/logros`, perfiles y Prode de Center Stage contra la línea base de 8.1). Después, un administrador ejecuta el primer recálculo en `/admin` y se revisan conteos y revocaciones antes de encender `ACHIEVEMENTS_AUTO=true`.
