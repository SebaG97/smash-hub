# Cuentas, roles y vinculación con jugadores

Misión SH-AUTH-01, decisión en [ADR-021](../adr/ADR-021.md). Operación y despliegue en [operations/accounts.md](../operations/accounts.md).

## Arquitectura

```text
Navegador ──(cookie sh_session HttpOnly + X-Requested-With)──▶ /api/v1/...  (mismo dominio en producción)
   │                                                              │
   │  Next: /ingresar /registro /recuperar /cuenta /admin/...     ├─ app/auth       cuentas, sesiones, roles, recuperación, auditoría
   │  Rutas /og/* reenvían la cookie a la API                     ├─ app/links      vinculación cuenta ↔ ficha de jugador
   │                                                              ├─ app/core/admin dependencia Admin de las rutas de organizadores
   └──────────────────────────────────────────────────────────────└─ app/prode      usa users.id y la vinculación activa
```

| Pieza | Archivo |
| --- | --- |
| Modelos de cuenta, sesión, token de recuperación y auditoría | `apps/api/app/auth/models.py` |
| Hash Argon2id y reglas de contraseña | `apps/api/app/auth/passwords.py` |
| Registro, ingreso, esperas progresivas, dirección del cliente, sesiones, recuperación, dependencias `MaybeUser`, `SignedUser`, `Member`, `Staff`, `Superadmin` | `apps/api/app/auth/service.py` |
| HTTP de la cuenta (`/api/v1/auth/*`) | `apps/api/app/auth/router.py` |
| HTTP de administración (`/api/v1/admin/*`) | `apps/api/app/auth/admin_router.py` |
| Vinculación (`/api/v1/links/*` y servicio) | `apps/api/app/links/` |
| Acceso administrativo de las rutas existentes | `apps/api/app/core/admin.py` |
| Primer superadministrador | `apps/api/app/cli/superadmin.py` |
| Web: sesión, organizador, pantallas | `apps/web/src/lib/session.ts`, `lib/admin.ts`, `components/account.tsx`, `components/admin-accounts.tsx`, `components/admin-panel.tsx` |

## Modelo de usuarios y roles

`users`: `username` (único, minúsculas), `email` (único, minúsculas; nulo solo en cuentas heredadas de start.gg), `password_hash` (Argon2id; nulo = no puede ingresar), `display_name`, `role` (`user` | `admin` | `superadmin`), `disabled_at`, `password_changed_at`, `last_login_at`.

| Capacidad | user | admin | superadmin |
| --- | :-: | :-: | :-: |
| Jugar el Prode, ver rankings y logros, editar su perfil | ✓ | ✓ | ✓ |
| Pedir vinculación con su ficha | ✓ | ✓ | ✓ |
| Herramientas de organizadores (seeding, rankings, importación, equipos, Prode) | | ✓ | ✓ |
| Revisar solicitudes, vincular y desvincular | | ✓ | ✓ |
| Buscar cuentas (sin ver correos) | | ✓ | ✓ |
| Ver correos, cambiar roles, desactivar/reactivar, cerrar sesiones ajenas, emitir enlaces de recuperación, ver estado y registro | | | ✓ |

Reglas que verifica el backend: el registro público no acepta `role` (422 por campo extra) y siempre crea `user`; nadie cambia su propio rol ni se desactiva; siempre queda al menos un superadmin activo; cambiar el rol o desactivar cierra las sesiones de esa cuenta.

## Sesiones

- Token aleatorio de 256 bits en la cookie `sh_session` (`HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` con `ENVIRONMENT=production`). La tabla `user_sessions` guarda su SHA-256, el vencimiento y la revocación.
- Duración: 30 días; 7 para `admin` y `superadmin` (se calcula al ingresar, por eso un cambio de rol fuerza un nuevo ingreso).
- Cada petición busca la sesión no revocada ni vencida (hora de la base) de una cuenta no desactivada, y lee el rol de la base: un cambio de rol o una desactivación rige en la siguiente petición.
- Revocación: salir (esa sesión), cambiar la contraseña (las demás), "Cerrar las demás" en `/cuenta`, recuperar la contraseña (todas), cambio de rol, desactivación o "Cerrar sesiones" de un superadmin (todas).
- Ingreso: usuario o correo. Errores indistinguibles para usuario inexistente y contraseña incorrecta, y una verificación Argon2 de igual costo en ambos casos. Cada fallo de una cuenta existente queda en la auditoría (`login_failed`, con la dirección).
- Sin bloqueos de cuenta: esperas progresivas en memoria (la API corre en una sola instancia; un reinicio las olvida). Por dirección y cuenta, 5 fallos libres y después 1 s, 2 s, 4 s… hasta 15 minutos: solo espera quien sigue fallando desde esa dirección. Por cuenta desde cualquier dirección, 20 fallos libres y como máximo 60 segundos: es todo lo que un tercero puede imponerle a una cuenta ajena. Por dirección contra cualquier cuenta, 30 libres y hasta 15 minutos. Los intentos rechazados durante una espera no se evalúan ni suman. La clave de cuenta es lo que se escribió, exista o no la cuenta, así que el 429 no revela cuentas. El ingreso correcto limpia la espera de esa cuenta. La respuesta 429 trae `Retry-After`. El registro admite 20 intentos por hora por dirección.
- La dirección del cliente sale del socket, salvo que `CLIENT_IP_HEADER` esté configurada (producción: `do-connecting-ip`, donde el ingress de App Platform pone la IP del visitante; `X-Forwarded-For` trae la del ingress). Solo se lee ese encabezado, solo su último valor (el que agrega el proxy) y solo si es una IP válida; si no, se usa el socket. Sin la variable no se confía en ningún encabezado. Antes de confiar en el valor en producción, verificarlo como indica el [runbook](../operations/accounts.md#procedimiento-de-despliegue).
- CSRF: `X-Requested-With: smashhub` en toda escritura con cookie (y en registro, ingreso y recuperación). Las lecturas administrativas (`GET`) no lo necesitan: CORS impide leerlas desde otro origen.

## Acceso administrativo

`app.core.admin.Admin` (y `MaybeAdmin` en las páginas con borradores) resuelve, en orden:

1. La sesión de una cuenta `admin` o `superadmin` → actor = su usuario. En escrituras exige el encabezado CSRF y registra `admin_request` en `auth_audit_entries`.
2. Solo durante la transición, `Authorization: Bearer <ADMIN_TOKEN>` → actor = `clave:<X-Admin-Name>`. Requiere `ADMIN_TOKEN_EXPIRES` vigente; cada uso se registra como `legacy_admin_request` y se loguea como advertencia.
3. Si no: 401 (sin sesión) o 403 (sesión sin rol).

Las rutas nuevas de `/api/v1/admin/*` usan `Staff` o `Superadmin`, que solo aceptan sesión: la clave compartida no gestiona cuentas.

## Vinculación de jugadores

- `player_links`: `user_id`, `player_id`, `method` (`request` | `admin` | `startgg_legacy`), `verification` (cómo se comprobó, obligatorio), `linked_by`/`linked_by_name`, y al desvincular `unlinked_at`, `unlinked_by`/`unlinked_by_name`, `unlink_reason`. Índices únicos parciales: una vinculación activa por cuenta y una por ficha.
- `player_link_requests`: `user_id`, `player_id`, `status` (`pending` | `approved` | `rejected` | `cancelled`), `code`, `evidence`, revisión (`reviewed_by_name`, `reviewed_at`, `review_note`). Una pendiente por cuenta (índice único parcial).

**A. Solicitud.** En `/cuenta` la persona busca su tag, elige la ficha y explica cómo comprobarlo. Recibe un código (`SH-XXXXXX`) que pone en la bio de su start.gg o muestra por el Discord de la comunidad o en persona. En `/admin/vinculaciones` un admin ve el código y la evidencia; para aprobar tiene que escribir cómo lo verificó (al menos 10 caracteres). Rechazar requiere un motivo que la persona ve. Si la ficha ya está tomada o la cuenta ya tiene una, la solicitud no se crea.

**B. Asignación directa.** En `/admin/vinculaciones` el admin busca la cuenta y la ficha, anota la verificación y vincula. Si la cuenta o la ficha ya tienen vinculación activa, responde 409; para reemplazarla hay que marcar "Reemplazar" y dar un motivo: las vinculaciones anteriores quedan cerradas con "Reemplazada: <motivo>" y se registra `link_replaced`. Desvincular pide motivo.

Nadie aprueba, rechaza ni vincula su propia cuenta (403): lo hace otro administrador.

## Prode

- Pronósticos (`prode_predictions`), historial, puntajes y logros referencian `users.id`; no dependen de la vinculación.
- Al liquidar, el jugador de cada cuenta sale de su vinculación activa (`links.startgg_ids_for_users`: vinculación → `external_identities` `player:<id>`). Sin vinculación, simplemente no hay logros "Fe en sí mismo" ni "Profecía autocumplida".
- `GET /prode/players/{player_id}/achievements` muestra los logros de la cuenta vinculada a esa ficha; al desvincular deja de mostrarlos, pero siguen en el perfil del pronosticador.
- Volver a liquidar un concurso recalcula sus logros con las vinculaciones vigentes en ese momento.
- Las cuentas desactivadas salen del ranking general y su perfil público responde 404; sus datos se conservan.

## Limitaciones conocidas

- **Correo:** el hub no tiene proveedor de correo y no hay recuperación por correo ni verificación del correo al registrarse. La única vía es el enlace de un solo uso que emite un superadmin; depende de que la persona pueda identificarse ante un administrador por un canal de confianza. Sumar correo más adelante requiere un proveedor SMTP y una nueva decisión.
- **Enumeración:** el registro informa si un usuario o correo ya existe (necesario para la experiencia); el ingreso y la recuperación no lo revelan.
- **Esperas:** un tercero que falle a propósito desde muchas direcciones puede hacer esperar a una cuenta como máximo 60 segundos entre intentos; nunca la bloquea. Las esperas viven en memoria: si la API pasara a más de una instancia, cada una llevaría su cuenta (habría que moverlas a un almacenamiento compartido).
- **Dirección del cliente:** DigitalOcean documenta que `do-connecting-ip` trae la IP del visitante, pero no que el ingress descarte una copia enviada por el cliente; por eso solo se usa el último valor y hay que verificarlo al desplegar. Si fallara, un atacante podría variar su dirección aparente, pero sigue limitado por la espera por cuenta (60 s como máximo entre intentos).
- **Cuentas heredadas de start.gg** (si las hubiera): conservan historial pero no pueden ingresar. Un superadmin no puede asignarles contraseña; la persona crea una cuenta nueva y, si hace falta, se la vincula a su ficha.
- **Sin 2FA** ni lista de sesiones por dispositivo (solo el total y "cerrar las demás").
- La cookie no usa el prefijo `__Host-` para funcionar igual en desarrollo (HTTP).
- Las rutas `/og/*` de Next reenvían la cookie del navegador a la API para generar imágenes de borradores; la API decide.
