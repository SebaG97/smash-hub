# Cuentas: configuración, primer superadministrador, transición y despliegue

Misión SH-AUTH-01 ([ADR-021](../adr/ADR-021.md), [arquitectura](../architecture/accounts.md)). Nada de esto se ejecutó contra producción.

## Migración necesaria

`0019_accounts` (sobre `0018`, que también está pendiente en producción si el Prode no se desplegó). Ver [schema.md](../database/schema.md#migración-0019-adr-021) y [migrations.md](migrations.md#revisión-0019--cuentas-propias).

- Agrega a `users`: `username`, `email`, `password_hash`, `role`, `password_changed_at`, `last_login_at`; renombra `banned_at` → `disabled_at`; quita `provider`, `provider_user_id`, `slug`, `startgg_player_id`.
- Crea `player_links`, `player_link_requests`, `password_reset_tokens` y `auth_audit_entries`.
- Datos: cada cuenta de start.gg existente recibe el usuario `sgg-<id de start.gg>` y queda sin correo ni contraseña; si su jugador de start.gg existe en el hub, se crea la vinculación `startgg_legacy`.
- Usa `gen_random_uuid()` (PostgreSQL 13 o superior).
- Probada en PostgreSQL 17 efímero: upgrade con datos heredados, downgrade a 0018 (las cuentas propias vuelven como `provider = 'local'`), re-upgrade, `alembic check` sin diferencias y roundtrip completo de la suite.

## Variables de entorno (API)

| Variable | Tipo | Uso |
| --- | --- | --- |
| `ADMIN_TOKEN` | secreto, opcional | Clave compartida heredada. Solo funciona con `ADMIN_TOKEN_EXPIRES`. Retirar al terminar la transición. |
| `ADMIN_TOKEN_EXPIRES` | fecha ISO con zona, opcional | Fin de la transición, p. ej. `2026-12-15T23:59:00-03:00`. Máximo 90 días desde el arranque (si no, la API no arranca). Sin ella, la clave no funciona. |
| `CLIENT_IP_HEADER` | opcional; en App Platform `do-connecting-ip` | Encabezado del proxy con la IP del visitante, para las esperas del ingreso y la auditoría. Solo se lee su último valor y solo si es una IP válida. Vacío: no se confía en ningún encabezado (local). |
| `CORS_ORIGINS` | existente | El primer origen es el de la web: con él se arman los enlaces de recuperación. |

No hay recuperación por correo ni variables SMTP: las contraseñas se recuperan con el enlace que emite un superadmin (abajo).

Se eliminan `STARTGG_OAUTH_CLIENT_ID`, `STARTGG_OAUTH_CLIENT_SECRET` y `STARTGG_OAUTH_REDIRECT_URI` (borrarlas de App Platform; la app OAuth de start.gg puede darse de baja). `STARTGG_API_TOKEN` no cambia: sigue sirviendo para leer torneos, inscriptos y resultados.

No hay secretos nuevos obligatorios: las sesiones y los tokens son aleatorios y se guardan como hash.

## Primer superadministrador

No hay usuarios ni contraseñas por defecto. El comando se niega si ya existe un superadministrador activo (después, los siguientes se nombran desde `/admin/usuarios`).

Recomendado (la contraseña nunca pasa por una terminal):

1. La persona se registra en `<sitio>/registro`.
2. Un operador, desde la consola del componente `api` en App Platform:
   ```sh
   python -m app.runtime superadmin promote --username <usuario>
   ```
   En local: `docker compose run --rm api python -m app.cli.superadmin promote --username <usuario>`.
3. La persona vuelve a ingresar (la promoción cierra sus sesiones) y ve "Admin" en el encabezado.

Alternativa sin registro web: `python -m app.runtime superadmin create --username <u> --email <correo>`. Pide la contraseña dos veces de forma oculta y exige una terminal interactiva; no la acepta como argumento ni variable de entorno.

Recuperación deliberada (por ejemplo, el único superadmin perdió el acceso): agregar `--additional`. Queda registrado con actor `cli`.

## Recuperación de contraseña asistida

1. La persona pide ayuda por el Discord de la comunidad o en persona. `/recuperar` le explica cómo.
2. Un superadmin confirma su identidad por ese canal (no por el nombre de usuario) y, en `/admin/usuarios`, toca "Enlace de recuperación" en esa cuenta.
3. El enlace aparece una sola vez. Se lo pasa por un mensaje directo; no se publica en canales abiertos.
4. La persona elige la contraseña nueva en `/recuperar/nueva`. El enlace deja de servir y se cierran todas sus sesiones.

El enlace vence a las 24 horas y deja de servir si se emite otro, si la cuenta se desactiva o si quien lo emitió deja de ser superadmin. En la base solo queda su hash. La auditoría registra quién lo emitió y cuándo se usó, nunca el token. Las respuestas con el token llevan `Cache-Control: no-store`, y el acceso HTTP no se loguea (`--no-access-log`); además el token viaja en el fragmento `#token=`, que el navegador no envía al servidor.

## Transición desde la clave compartida

| Fase | Qué se hace | Cómo se verifica |
| --- | --- | --- |
| 1. Despliegue | Migración 0019 y la nueva versión. `ADMIN_TOKEN` sigue, con `ADMIN_TOKEN_EXPIRES` a 2–4 semanas. | `/admin` ofrece "Ingresar con tu cuenta" y, plegada, la clave. |
| 2. Cuentas | Nombrar el primer superadmin (arriba). Cada organizador se registra y el superadmin le da el rol `admin` en `/admin/usuarios`. Nada de cuentas compartidas. | `/admin/usuarios` → Estado: cantidad de administradores. |
| 3. Uso | Los organizadores trabajan con su cuenta. Los registros de seeding/Prode/equipos muestran su usuario en vez de `clave:<nombre>`. | Estado → "Último uso" de la clave; `GET /api/v1/admin/audit?action=legacy_admin_request`. |
| 4. Retiro | Cuando la clave lleve días sin usarse (o al vencer), borrar `ADMIN_TOKEN` y `ADMIN_TOKEN_EXPIRES` de App Platform y redesplegar. | Estado → "Clave compartida: retirada"; un `Authorization: Bearer` responde 401. |

La fecha es obligatoria a propósito: si nadie retira la clave, deja de funcionar sola. Extenderla requiere cambiar la variable (máximo 90 días cada vez) y queda a la vista en el estado.

## Procedimiento de despliegue

1. **Antes.** Backup de la base. Revisar el SQL de `0018` (si no se aplicó) y `0019`. Confirmar PostgreSQL ≥ 13.
2. **Variables.** En el componente `api`: borrar `STARTGG_OAUTH_*`; agregar `ADMIN_TOKEN_EXPIRES` (si se mantiene `ADMIN_TOKEN`) y `CLIENT_IP_HEADER=do-connecting-ip`. El App Spec de `infra/digitalocean/app.yaml` ya las declara.
3. **Migración.** Con el job aprobado del runbook ([digitalocean-first-deploy.md](digitalocean-first-deploy.md)): `APPROVED_MIGRATION=0018` y luego `APPROVED_MIGRATION=0019` (o directamente `0019`, que incluye 0018). Nunca `head` implícito.
4. **Código.** Desplegar API y web juntas: la web nueva usa `/api/v1/auth/login` y la API nueva ya no tiene `/auth/startgg/*`.
5. **Verificar.** `GET /api/v1/health/ready`; registrarse con una cuenta de prueba; ingresar/salir; `GET /api/v1/auth/me` devuelve `legacy_admin_key` según lo configurado; la respuesta de ingreso trae `Set-Cookie` con `HttpOnly; Secure; SameSite=lax`. **Dirección del cliente:** fallar un ingreso con una cuenta de prueba enviando un `do-connecting-ip` falso (`curl -H 'do-connecting-ip: 203.0.113.9' -H 'X-Requested-With: smashhub' ...`) y revisar en `GET /api/v1/admin/audit?action=login_failed` que el `ip` registrado sea la IP pública real y no `203.0.113.9`. Si apareciera la falsa, el ingress deja pasar la copia del cliente: quitar `CLIENT_IP_HEADER` (las esperas por cuenta siguen funcionando) y consultarlo con DigitalOcean.
6. **Primer superadmin** y fases 2–4 de la transición.
7. **Rollback.** Preferir una corrección hacia adelante. Si hace falta volver, `alembic downgrade 0018` conserva cuentas y pronósticos pero pierde contraseñas, roles, vinculaciones, solicitudes, tokens y auditoría de cuentas (restaurar desde el backup si se necesitan), y la versión anterior volvería a requerir OAuth de start.gg.

## Desarrollo local

```sh
docker compose run --rm api alembic upgrade head
# Registrate en http://localhost:3000/registro y después:
docker compose run --rm api python -m app.cli.superadmin promote --username <usuario>
```

En local la cookie no lleva `Secure` (HTTP). La web en `:3000` y la API en `:8000` comparten la cookie porque las cookies no distinguen puertos; los `fetch` usan `credentials: "include"`.
