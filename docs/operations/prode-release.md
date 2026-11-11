# Publicación del Prode y las cuentas propias (SH-PRODE-RELEASE-01)

Estado al 11/11/2026. Nada de esto se ejecutó contra producción: no se tocaron variables, base, migraciones ni `main`.

Qué se publica: el Prode (Misión SH-PRODE-01, [prode.md](../architecture/prode.md)) y las cuentas propias con roles y vinculación de jugadores (SH-AUTH-01, [ADR-021](../adr/ADR-021.md), [accounts.md](accounts.md)). El reglamento de Center Stage 2026 (SH-RULES-01) ya está en producción y no cambia.

## 1. Integración con `main`

| Rama | Commits |
| --- | --- |
| `origin/main` | `e44fabf` reglamento (cherry-pick de `fdad1b0` sin la pestaña Prode, el CSS de Prode/cuentas ni la línea SH-AUTH-01 del README) sobre `8648fcf`. |
| `feature/prode` | `db54a4a` Prode · `4aeab5e` cuentas propias · `fdad1b0` reglamento · **`6719d92` merge de `origin/main`** · commit de esta documentación. |

- Base común: `8648fcf`. `main` no tiene commits que falten en `feature/prode`, así que `main` puede avanzar por *fast-forward* (`git merge --ff-only feature/prode`).
- Conflictos del merge: `README.md`, `apps/web/src/app/globals.css`, `apps/web/src/components/tournament-preview.tsx` y `apps/web/tests/rulebooks.test.tsx`. Se resolvieron con la versión de `feature/prode`: `git diff fdad1b0 e44fabf` solo tiene líneas eliminadas (las del Prode), o sea que `feature/prode` ya contenía todo lo de `main`. El árbol resultante es idéntico al de `fdad1b0`.
- Reglamento preservado: `git diff origin/main HEAD` sobre `public/reglamentos/center-stage-2026-v1.0.pdf`, `src/lib/rulebooks/`, `src/components/rulebook.tsx`, `src/app/reglamentos/[id]/page.tsx` y `docs/architecture/reglamentos.md` está vacío. Los únicos cambios en archivos compartidos son la pestaña «Prode» (antes de «Reglamento») en la previa, su CSS y la línea del README.
- Sin duplicados: un solo `RulebookPanel`, una sola ruta `/reglamentos/[id]`, un solo registro de reglamentos y un solo PDF.

## 2. Cambios de esta misión

- Merge `6719d92` (sin cambios de código: solo resolución de conflictos).
- Esta guía y su enlace desde [digitalocean-first-deploy.md](digitalocean-first-deploy.md).
- No hizo falta corregir código: todas las validaciones pasaron.

## 3. Pruebas ejecutadas (sobre `6719d92`)

| Verificación | Resultado |
| --- | --- |
| API: `pytest -q` en PostgreSQL 17 efímero (`compose.test.yaml`) | 296 passed |
| API: `ruff check .` y `ruff format --check .` | sin errores |
| API: `alembic heads` | `0019 (head)`, una sola cabeza |
| Web: `npm test` (Vitest) | 30 archivos, 119 tests passed |
| Web: `npm run typecheck`, `npm run lint`, `npm run format:check` | sin errores |
| Web: `npm run build` | OK; rutas `/prode`, `/prode/u/[id]`, `/registro`, `/ingresar`, `/cuenta`, `/recuperar`, `/admin/usuarios`, `/admin/vinculaciones`, `/reglamentos/[id]` |

Prueba de humo HTTP en un proyecto Docker aislado (Postgres en tmpfs, sin tocar la base local), con la misma ruta que usa producción: `APPROVED_MIGRATION=0017`, `0018` y `0019` con `python -m app.runtime migrate`, y la API levantada con `python -m app.runtime`:

- `alembic current` = `0019 (head)`; sin `APPROVED_MIGRATION` el migrador se niega.
- Público sin sesión: torneos y Prode responden 200; `/auth/me` da `user: null`; `/auth/startgg/login` da 404.
- Registro sin inscripción a torneos (201), rol inicial `user`, cierre e inicio de sesión.
- Un `user` recibe 403 en `/admin/users`.
- `python -m app.runtime superadmin promote --username seba`: promueve, cierra sus sesiones y se niega a un segundo superadmin sin `--additional`.
- El superadmin ingresa con su cuenta, nombra `admin` a otro usuario; ese admin no puede autoascenderse.
- Vinculación directa jugador ↔ cuenta (201) visible en `/links/mine`; auditoría visible en `/admin/audit`.
- `/admin/status` informa la clave compartida como configurada y activa. La clave **no** abre `/admin/users`: es intencional (las rutas de cuentas exigen sesión personal, `test_auth.py`), solo abre rutas de organizador (seeding, rankings, importación, equipos, Prode).

Recorridos cubiertos por la suite (no repetidos a mano):

| Recorrido | Tests |
| --- | --- |
| Reglamento público, pestaña en la previa, lector y PDF | `apps/web/tests/rulebooks.test.tsx` |
| Campeón, subcampeón y Top 8; validaciones; modificar antes del cierre; 409 después | `test_prode.py::test_prode_from_sign_in_to_achievements`, `test_contest_locks_itself_when_the_event_starts` |
| Puntos, ranking y desempates con resultados de doble eliminación | `test_results_and_scores_follow_double_elimination_placements`, `test_ranking_breaks_ties_and_shares_full_ties` |
| Sin login de start.gg | `test_start_gg_sign_in_is_gone` |
| Roles, auditoría, recuperación asistida, sesiones, throttling, IP del proxy | `test_auth.py` |
| Solicitudes y vinculaciones de jugadores | `test_links.py` |
| UI de cuentas y Prode | `apps/web/tests/accounts.test.tsx`, `prode.test.tsx` |

Integración con start.gg: el Prode toma inscriptos y resultados con `STARTGG_API_TOKEN` (token de servidor, `app/integrations/startgg/client.py`). No queda código de OAuth en API ni web; la importación y la sincronización existentes no cambiaron.

## 4. Requisitos de DigitalOcean

Procedimiento de base: «Procedimiento de despliegue» en [accounts.md](accounts.md). Requisitos confirmados contra el código:

| Ítem | Requisito |
| --- | --- |
| Migraciones | Producción debe estar en `0017` (último log del job `migrate`: `Running upgrade 0016 -> 0017`). `0018` crea las tablas del Prode y `users`/`user_sessions`; `0019` amplía `users` y crea vinculaciones, solicitudes, tokens de recuperación y auditoría. No modifican tablas existentes de torneos, jugadores ni seeding. Como `0018` nunca se aplicó en producción, `users` está vacía y la conversión de cuentas de start.gg de `0019` no afecta a nadie. Requiere PostgreSQL ≥ 13 (`gen_random_uuid()`). |
| `APPROVED_MIGRATION` | `0019` en el componente `migrate` (aplica 0018 y 0019 en el mismo job). Sin un valor conocido el job falla a propósito. |
| `ADMIN_TOKEN` | Se conserva durante la transición. Sigue exigiendo ≥ 24 caracteres (igual que hoy). |
| `ADMIN_TOKEN_EXPIRES` | **Obligatoria para conservar la clave**: sin ella la clave deja de funcionar al desplegar. Fecha ISO **con zona horaria** y **≤ 90 días** desde cada arranque de la API; si no, la API **no arranca**. Sugerido: `2026-12-15T23:59:00-03:00`. |
| `CLIENT_IP_HEADER` | `do-connecting-ip` en el componente `api`. Se valida en el paso de verificación. |
| `STARTGG_OAUTH_*` | Si existieran en el panel, borrarlas (la API las ignora; quedarían como secretos inútiles). |
| `STARTGG_API_TOKEN` | Sin cambios. Necesario para abrir y liquidar el Prode. |
| Web | Sin variables nuevas (`NEXT_PUBLIC_API_URL=/api/v1` como hoy). |
| Dependencias | API: `argon2-cffi` (y bindings, cffi, pycparser) con wheels para Linux; la imagen de prueba Python 3.13 las instaló sin compilar. Web: sin cambios. |
| Primer superadmin | `python -m app.runtime superadmin promote --username <usuario>` desde la consola del componente `api` (ver §6). |

## 5. Procedimiento de publicación

Requiere autorización explícita antes de empezar. App Platform redespliega solo al guardar variables de entorno, así que el orden importa: si el código nuevo arrancara con la base en `0017`, el Prode y las cuentas fallarían.

1. **Backup.** Panel → Databases → el clúster → Backups (o `pg_dump` con el rol migrador). Anotar la hora.
2. **Revisión actual.** En el último despliegue, logs del job `migrate`: debe figurar `0017`. Si no, detenerse.
3. **Publicar el código en `main`** (con `deploy_on_push: false` no despliega nada):
   ```sh
   git checkout main
   git pull --ff-only origin main
   git merge --ff-only feature/prode
   git push origin main
   ```
4. **Aplicar todos los cambios de configuración en un solo despliegue.** Recomendado con doctl:
   ```sh
   doctl apps spec get <app-id> > /tmp/spec.yaml
   # Editar /tmp/spec.yaml:
   #   job migrate  -> APPROVED_MIGRATION: "0019"
   #   service api  -> agregar ADMIN_TOKEN_EXPIRES: "2026-12-15T23:59:00-03:00"
   #                   agregar CLIENT_IP_HEADER: do-connecting-ip
   #                   quitar STARTGG_OAUTH_CLIENT_ID / _SECRET / _REDIRECT_URI si estuvieran
   #   (los secretos aparecen cifrados como EV[...]: no tocarlos)
   doctl apps update <app-id> --spec /tmp/spec.yaml
   ```
   Desde el panel: primero `APPROVED_MIGRATION=0019` en `migrate` (el despliegue que dispara ya trae el código nuevo y migra antes de arrancar) y después las dos variables de `api`. Entre ambos despliegues la clave compartida no funciona por unos minutos; nadie queda afuera de forma definitiva.
5. **Seguir el despliegue.** El job `migrate` debe mostrar `Running upgrade 0017 -> 0018` y `0018 -> 0019`; después arrancan `api` y `web`. Si el job falla, App Platform mantiene la versión anterior en línea.
6. **Verificar** (con una cuenta de prueba, nunca la del superadmin):
   - `GET /api/v1/health/ready` → 200.
   - `/reglamentos/center-stage-2026` y el PDF `/reglamentos/center-stage-2026-v1.0.pdf` abren; `/previa/center-stage-2026` muestra las pestañas «Prode» y «Reglamento».
   - `/registro` → crear cuenta; salir; `/ingresar`. La respuesta de ingreso trae `Set-Cookie` con `HttpOnly; Secure; SameSite=lax`.
   - `GET /api/v1/auth/me` → `legacy_admin_key: true`.
   - IP real: el ingreso fallido con `do-connecting-ip` falso de [accounts.md](accounts.md) (paso 5); si la auditoría registra la IP falsa, quitar `CLIENT_IP_HEADER`.
   - `/prode` carga sin sesión.
7. **Primer superadmin** (§6). Luego cada organizador se registra y el superadmin le da rol `admin` en `/admin/usuarios`.
8. **Abrir el Prode** de Center Stage: con sesión de admin, `/previa/center-stage-2026` → pestaña Prode → «Abrir Prode». Se cierra solo al empezar el evento (o a mano). Terminado el torneo: «Liquidar con start.gg».
9. **Retirar la clave compartida** cuando `/admin/usuarios` → Estado muestre que no se usa (o al vencer): borrar `ADMIN_TOKEN` y `ADMIN_TOKEN_EXPIRES` y redesplegar.

### Rollback

Preferir una corrección hacia adelante. Si hay que volver al código anterior (`e44fabf`):

- **No hace falta bajar la base.** 0018/0019 solo agregan tablas que la versión anterior no lee; el reglamento y el resto del hub funcionan igual sobre una base en `0019`. Así se conservan cuentas y pronósticos para volver a publicar.
- **Trampa del job `migrate`:** el código anterior no conoce la revisión `0019` y el job fallaría tanto con `0019` como con `0017` (Alembic no encuentra la revisión instalada). Para desplegar el código anterior hay que **quitar temporalmente el job `migrate` del spec** (o usar el «Rollback» del panel al despliegue previo) y volver a agregarlo con `0019` al republicar.
- `alembic downgrade 0018` solo si es imprescindible: pierde contraseñas, roles, vinculaciones, solicitudes, tokens y auditoría de cuentas ([accounts.md](accounts.md)).

## 6. Primer superadministrador

No hay usuarios ni contraseñas por defecto. Recomendado (la contraseña nunca pasa por una terminal):

1. La persona se registra en `https://<sitio>/registro` (usuario, correo y contraseña).
2. Un operador abre la consola del componente **`api`** en App Platform (Console) y ejecuta:
   ```sh
   python -m app.runtime superadmin promote --username <usuario>
   ```
   Respuesta esperada: `Listo: <usuario> es superadministrador. Ingresá en /ingresar.`
3. La persona vuelve a ingresar (la promoción cierra sus sesiones) y ve «Admin» en el encabezado. En `/admin/usuarios` → Estado figura 1 superadministrador.

- El comando se niega si ya hay un superadmin activo. Los siguientes se nombran desde `/admin/usuarios`. Recomendado: nombrar un segundo superadmin para no depender de una sola persona.
- Sin registro web: `python -m app.runtime superadmin create --username <u> --email <correo>` (pide la contraseña dos veces de forma oculta; requiere terminal interactiva).
- Recuperación si el único superadmin pierde el acceso: agregar `--additional`. Queda auditado con actor `cli`.

## 7. Riesgos pendientes

| Riesgo | Mitigación |
| --- | --- |
| `ADMIN_TOKEN_EXPIRES` mal formada o > 90 días: la API no arranca. | Usar el formato sugerido; App Platform deja la versión anterior si el health check falla. Si se extiende, recordar que el límite cuenta desde cada arranque. |
| Olvidar `ADMIN_TOKEN_EXPIRES`: la clave compartida deja de funcionar. | Los organizadores ingresan con cuenta propia apenas exista el superadmin (paso 7). |
| `do-connecting-ip` no confiable en el ingress. | Prueba del paso 6; si falla, quitar `CLIENT_IP_HEADER` (el límite por cuenta sigue). |
| Rollback de código con el job `migrate` activo falla. | Ver «Rollback». |
| Argon2id usa ~64 MiB por hash en una instancia de 0.5 GB. | Ingresos simultáneos acotados por el throttling; vigilar memoria de `api` el día del torneo y subir de tamaño si hace falta. |
| El cierre automático depende de la hora de inicio y el estado que informe start.gg. | El organizador puede cerrar a mano antes de empezar. |
| La liquidación depende de que start.gg tenga los resultados finales. | Liquidar después de cerrar el evento en start.gg; liquidar de nuevo recalcula igual. |
| La recuperación de contraseña es asistida (sin correo). | Proceso en [accounts.md](accounts.md); contar con al menos dos superadmins. |
| No se validó contra la cuenta de DigitalOcean (spec, consola, backups). | Pasos 1, 2 y 5 con revisión humana. |
