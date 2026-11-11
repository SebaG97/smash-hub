# Despliegue del Prode y las cuentas propias (SH-PRODE-AUTH-DEPLOY-01)

Fecha: 11/11/2026. App de DigitalOcean: `smash-hub-app` (`https://smash-hub-app-d4eh4.ondigitalocean.app`). Guía previa: [prode-release.md](prode-release.md).

## 1. Código publicado

- `origin/main` avanzó por *fast-forward* de `e44fabf` (reglamento) a **`3abb5a5`**: `db54a4a` Prode · `4aeab5e` cuentas propias · `fdad1b0` reglamento · `6719d92` merge · `3abb5a5` guía de publicación.
- El push no disparó ningún despliegue: los componentes no definen `deploy_on_push` (equivale a `false`). Inmediatamente después del push, `/prode` y `/api/v1/auth/me` seguían respondiendo 404 (código anterior).

## 2. Estado previo verificado (con doctl, contexto `smashhub`)

| Ítem | Resultado |
| --- | --- |
| Despliegue activo previo | `a9a6125a…`, ACTIVE, `web`/`api`/`migrate` en `e44fabf`. |
| Spec | `web` (apps-s-1vcpu-1gb-fixed), `api` (apps-s-1vcpu-0.5gb), job `migrate` `PRE_DEPLOY` con `APPROVED_MIGRATION=0017` y `MIGRATION_DATABASE_URL`. Ingress `/api` → `api`, `/` → `web`. Sin variables `STARTGG_OAUTH_*`. |
| Revisión de la base | `0017`, deducida: el despliegue activo terminó con el job `migrate` en `0017` y ese código no tenía `0018`/`0019`. Los logs del job ya no estaban disponibles. |
| Base | Clúster `segir-db-1`, PostgreSQL 18, base `smash-hub`. |

## 3. Backup

- **No se hizo `pg_dump` previo.** El token de doctl no podía leer credenciales de la base (DigitalOcean las devuelve como `********`), y el propietario autorizó continuar con los backups automáticos.
- Backups automáticos diarios disponibles; el último antes del despliegue fue el 11/11/2026 00:43 UTC (~97 MB). Los cambios posteriores solo se recuperan con la restauración a un punto en el tiempo de DigitalOcean.
- Quedaron dos archivos vacíos de los intentos fallidos en `C:\Users\user\smashhub-backups\` (sin datos; se pueden borrar).

## 4. Configuración y despliegue

El token de doctl no tiene permisos sobre Apps (403), así que el propietario aplicó el spec desde el panel, en una sola edición:

| Componente | Cambio |
| --- | --- |
| job `migrate` | `APPROVED_MIGRATION`: `0017` → `0019` |
| `api` | `ADMIN_TOKEN_EXPIRES=2026-12-15T23:59:00-03:00` (nueva) |
| `api` | `CLIENT_IP_HEADER=do-connecting-ip` (nueva) |
| resto | Sin cambios; `ADMIN_TOKEN` y demás secretos conservados. |

El panel informó el despliegue como **Healthy**. El ID del despliegue y el commit no se pudieron leer por API (sin permiso de Apps); que corre `3abb5a5` se confirma por comportamiento: las rutas nuevas responden y `/auth/startgg/login` da 404.

### Migraciones `0018` y `0019`

Confirmadas por comportamiento (sin acceso a los logs del job): `/api/v1/prode` lee `prode_contests` (0018); el registro guarda correo y rol (columnas de `users` de 0019); `/links/mine` y `/auth/sessions` responden 200 (tablas de 0018/0019). Ningún endpoint devolvió 500.

## 5. Verificación en producción

Con una cuenta de prueba exclusiva (`qa_deploy_1111`, correo `@example.com`, contraseña aleatoria no guardada). No se abrió, modificó ni liquidó ningún Prode.

| Verificación | Resultado |
| --- | --- |
| `GET /api/v1/health/ready` | 200 |
| Páginas `/`, `/prode`, `/registro`, `/ingresar`, `/cuenta`, `/recuperar`, `/admin/usuarios`, `/admin/vinculaciones`, `/previa/center-stage-2026-1` | 200 |
| Reglamento `/reglamentos/center-stage-2026` | 200 |
| PDF `/reglamentos/center-stage-2026-v1.0.pdf` | 200, `application/pdf`, 370 765 bytes, firma `%PDF-` |
| Previa de Center Stage | Pestañas «Prode» y «Reglamento» presentes; 89 inscriptos y seeding cargados. |
| `/auth/me` sin sesión | `user: null`, `legacy_admin_key: true` (la clave compartida sigue activa hasta el 15/12). |
| Login de start.gg | `/auth/startgg/login` → 404 (retirado). |
| Escrituras sin el encabezado de la web | 403 (protección CSRF activa). |
| Registro | 201, rol `user`. |
| Cookie de sesión | `HttpOnly; Secure; SameSite=lax; Max-Age=2592000`. |
| Cierre e inicio de sesión | Logout 204 → `user: null`; login 200 → la sesión persiste en `/auth/me`. |
| `/auth/sessions`, `/links/mine` | 200 |
| `user` en `/admin/users`, `/admin/link-requests`, `/admin/links`, `/admin/audit`, `/admin/status` | 403 |
| `user` intentando abrir un Prode | 403 |
| Anónimo en `/admin/users` | 401 |
| Prode público | `/api/v1/prode` 200, sin concursos ni ranking todavía. |

### Cierre de predicciones de Center Stage

El Prode de `center-stage-2026-1` **todavía no está abierto** (404 «Este torneo todavía no tiene Prode»). Al abrirlo, el cierre se toma del `startAt` del evento en start.gg (o del torneo). Hoy start.gg informa el torneo para el **14/11/2026 19:00 UTC = 16:00 (UTC−3)**, en Asunción. Hay que confirmar la hora mostrada después de abrirlo.

Nota: el slug de start.gg `center-stage-2026` (sin `-1`) es otro torneo (Chicago, 07/11). El torneo local es `center-stage-2026-1`.

## 6. Primer superadministrador

Pendiente: el propietario se registra en `/registro` y un operador ejecuta en la consola del componente `api`:

```sh
python -m app.runtime superadmin promote --username <usuario>
```

Procedimiento completo en [prode-release.md §6](prode-release.md#6-primer-superadministrador).

## 7. Pendientes e incidencias

| Pendiente | Detalle |
| --- | --- |
| Primer superadmin | §6. |
| IP real (`do-connecting-ip`) | Se envió un ingreso fallido de `qa_deploy_1111` con `do-connecting-ip: 203.0.113.77` y `X-Forwarded-For: 203.0.113.78`. Con el superadmin, revisar en `/admin/usuarios` → Auditoría: si figura `203.0.113.77`, quitar `CLIENT_IP_HEADER` del `api`. |
| Cuenta de prueba | Desactivar `qa_deploy_1111` desde `/admin/usuarios`. |
| Abrir el Prode de Center Stage | Con sesión de admin: `/previa/center-stage-2026-1` → Prode → «Abrir Prode»; verificar la hora de cierre (§5). |
| Backup manual | No hay `pg_dump` previo al despliegue (§3). |
| Permisos de doctl | El token `smashhub` no puede leer credenciales de la base ni la app: los backups manuales y los despliegues futuros por CLI requieren otro token. |
| Clave compartida | Vence el 15/12/2026 23:59 (−03:00). Retirar `ADMIN_TOKEN` y `ADMIN_TOKEN_EXPIRES` cuando los organizadores usen sus cuentas. |
