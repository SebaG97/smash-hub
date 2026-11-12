# Navegación principal y menú de usuario (Misión SH-UI-01)

Fecha: 12 de noviembre de 2026. Estado: implementado, sin desplegar.

## Qué cambia para el visitante

### Menú de usuario

Antes, el header mostraba `Nombre · Admin · Salir` como texto suelto y no era evidente que el nombre llevaba a la cuenta. Ahora, con sesión iniciada, hay un botón con ícono de usuario, el nombre visible y un chevron. Al abrirlo se muestra:

| Elemento | Destino | Quién lo ve |
| --- | --- | --- |
| Nombre visible y `@usuario` | (encabezado del menú) | todos |
| Mi cuenta | `/cuenta` | todos |
| Administración | `/admin` | solo `admin` y `superadmin` (`isStaff`) |
| Cerrar sesión | `logout()` existente (`POST auth/logout`) | todos |

Sin sesión, se mantiene el enlace «Ingresar» de siempre. El acceso con clave de administrador heredada (`AdminBadge`) no cambia.

Comportamiento:

- Se abre y cierra con clic, toque, `Enter` o `Espacio` (es un `<button>`).
- `Escape` lo cierra y devuelve el foco al botón; un clic o un foco fuera del menú también lo cierra, igual que seguir uno de sus enlaces.
- Patrón *disclosure*: el botón expone `aria-expanded` y `aria-controls`; el panel es una lista de enlaces que se recorre con `Tab`. Nombre accesible del botón: «Mi perfil: <nombre>».
- En pantallas de 420 px o menos el botón muestra solo ícono y chevron; el nombre sigue disponible para lectores de pantalla y dentro del menú.

### Pestaña «Previas»

Nueva entrada en la navegación principal entre «Seeding» y «Prode», que lleva a `/previas`. La página lista **todos** los próximos torneos de Smash Ultimate en Paraguay anunciados en start.gg (no solo Center Stage), con fecha, lugar, inscritos y un enlace a la previa de cada uno (`/previa/<slug>`).

La pestaña queda marcada (`aria-current="page"`) tanto en `/previas` como en cualquier `/previa/<slug>`.

Estados:

- **Cargando**: «Cargando datos…» (`role="status"`).
- **Vacío**: «No hay torneos anunciados por ahora» con un enlace a los torneos anteriores (`/tournaments`).
- **start.gg no disponible** (la API responde `unavailable: true` sin datos en caché): aviso `role="alert"`.
- **Error de la API**: «No se pudieron cargar los datos.» con botón «Reintentar».

### Header responsive

- **Más de 1180 px**: una sola fila horizontal (marca, navegación, menú de usuario), como antes.
- **1180 px o menos**: la navegación pasa a su propia fila de ancho completo y **se ajusta en varias líneas** en vez de desplazarse horizontalmente con la barra oculta. Así todas las secciones se ven sin deslizar en celulares. El menú de usuario queda alineado a la derecha; en 320 px baja a su propia línea, sin superponerse.
- El panel del menú tiene un ancho máximo de `100vw - 32px` y se alinea al borde derecho del botón, por lo que no se sale de la pantalla.

Las demás barras `nav` del sitio (pestañas de la previa, índice del reglamento) conservan su comportamiento anterior: el ajuste aplica solo a `.site-header > nav`.

## Implementación

No hay cambios en la API, la base de datos, la autenticación, los permisos ni las sesiones. La página `/previas` reutiliza el endpoint existente `GET /api/v1/insights/calendar` (el mismo del calendario de la portada, con caché de una hora en la API) y el componente `Resource` para carga y errores; la previa en sí sigue en `/previa/[slug]`.

| Pieza | Ubicación |
| --- | --- |
| Entrada «Previas» en el menú | `apps/web/src/lib/modules.ts` |
| Marca de sección activa (`/previas` y `/previa/*`) | `apps/web/src/components/nav-links.tsx` |
| Menú de usuario (`AccountBadge` → `UserMenu`) | `apps/web/src/components/account.tsx` |
| Lista de previas | `apps/web/src/components/previews-list.tsx` |
| Página | `apps/web/src/app/previas/page.tsx` |
| Tipo `CalendarItem` (ahora exportado) | `apps/web/src/components/insights.tsx` |
| Estilos | `apps/web/src/app/globals.css`, secciones `responsive`, `user menu (SH-UI-01)` y `previas (SH-UI-01)` |
| Pruebas | `apps/web/tests/accounts.test.tsx`, `apps/web/tests/previews-list.test.tsx` |

Sin cambios en: Prode y predicciones, cuentas y autenticación, vinculaciones con jugadores, reglamentos y PDF, integración con start.gg, horarios de torneos.

## Validación

- `npm run lint`, `npm run typecheck`, `npx vitest run` (31 archivos, 125 pruebas) y `npm run build` sin errores. Las pruebas nuevas cubren: menú por rol (`user` sin «Administración»; `admin` y `superadmin` con ella), cierre con `Escape` (foco de vuelta al botón), clic afuera y al seguir un enlace, cierre de sesión desde el menú; `/previas` con datos, vacía, start.gg no disponible y error de la API; posición de «Previas» entre «Seeding» y «Prode» y su marca activa.
- Verificación en navegador (Edge sin interfaz, `next dev` contra una API simulada) en 1366, 1024, 390 y 320 px, sin sesión y con roles `user`, `admin` y `superadmin`: sin desplazamiento horizontal, todas las pestañas dentro de la pantalla, panel del menú dentro del viewport, apertura con `Enter`, `Tab` hacia «Mi cuenta», cierre con `Escape` y con clic afuera. Flujo completo: portada → «Previas» → previa de un torneo (pestaña marcada) → «Mi cuenta» (el menú se cierra al navegar) → «Cerrar sesión» (vuelve «Ingresar»).

`npx prettier --check .` reporta avisos en el checkout de Windows por finales de línea CRLF también sin estos cambios; los archivos modificados pasan la verificación.
