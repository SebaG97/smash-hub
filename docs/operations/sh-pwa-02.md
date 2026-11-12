# SH-PWA-02 — Instalación en Android y anuncio compacto

Fecha: 12/11/2026. Base: [SH-PWA-01](sh-pwa-01.md), desplegada en producción. Estado: **integrado en `main` y con push (`366e566`), sin desplegar.** DigitalOcean respondió 403 y el despliegue de `web` queda pendiente de hacerse a mano. Producción sigue con SH-PWA-01: ver la [sección 9](#9-publicación-resultados-reales). No hubo pruebas en Android ni iPhone físicos.

## 1. Diagnóstico de la instalación en Android

Se probó contra producción (`https://smashclubpy.com`) con Chrome real de computadora en modo headless, emulando un Pixel (390 × 844, user agent de Chrome Android) y con un perfil nuevo. **No es un Android físico:** el Chrome de escritorio no aplica todas las reglas de Chrome Android.

| Punto revisado | Resultado |
| --- | --- |
| Manifest e íconos en producción | `/manifest.webmanifest` (`application/manifest+json`) y los cuatro íconos responden 200. `Page.getInstallabilityErrors` en `/install`: **ninguno**. |
| Captura global de `beforeinstallprompt` | Funciona. El evento llegó entre 0,7 y 1,2 s después de cargar. El script de `<head>` lo guardó (`__smashInstallPrompt`) y el botón apareció. |
| Abrir `/install` directo frente a navegar desde el inicio | Igual en los dos casos: el evento capturado en el inicio se conserva al navegar del lado del cliente y el botón aparece en `/install`. |
| **Visibilidad del botón** | **Problema de código.** A 390 × 844 el botón quedaba en y = 767, al pie de la pantalla: estaba debajo del logo de 112 px y de las cuatro ventajas. En celulares más chicos quedaba fuera de la primera pantalla y había que desplazarse para encontrarlo. |
| Navegadores internos | **Detección incompleta.** Solo se reconocían Instagram, Facebook, TikTok, Line y Twitter. No se detectaban WhatsApp, la app de Google (lo que abren algunos lectores de QR) ni cualquier WebView de Android (`; wv)`). Además, el aviso no daba un camino para salir del navegador interno. |
| Instalación previa | **Caso sin cubrir.** Si Smash Hub ya está instalada, Chrome no vuelve a mandar `beforeinstallprompt`. La página mostraba «Cómo instalar», como si faltara instalarla. |
| Estado mientras Chrome decide | **Caso sin cubrir.** No había diferencia visible entre «todavía no llegó el evento» y «el navegador no lo va a ofrecer». |
| Restricciones de Chrome | Chrome decide si manda el evento y cuándo. Puede no ofrecerlo en la primera visita (exige cierta interacción con el sitio), si la app ya está instalada, si la persona lo rechazó hace poco, en pestañas abiertas desde otra app (Custom Tabs) y en WebView. En esos casos **no hay nada que el código pueda forzar**: solo queda el menú ⋮ → Instalar aplicación. |

**Conclusión:** el mecanismo de captura de SH-PWA-01 funcionaba y no se cambió. Lo que dificultaba instalar en Android era de presentación y de detección: el botón quedaba fuera de la vista, los navegadores internos más comunes no se reconocían y no había estados claros. El resto depende de Chrome.

## 2. Cambios realizados

### Instalación (`/install`)

- **El botón va primero.** Debajo del nombre hay un panel con el estado y las acciones, antes de las ventajas. «Instalar Smash Hub» es más grande y ocupa todo el ancho en el celular. En pantallas de hasta 580 px el logo baja a 64 px; en las de hasta 380 px se oculta la bajada. Medido en Chrome: el botón queda dentro de la primera pantalla a 390 × 844 (y = 522), 360 × 640 (y = 462) y 320 × 568 (y = 514).
- **Estados explícitos** (`data-phase` en el panel, texto en `role="status"`):
  - **Disponible:** llegó el evento. «Tu navegador permite instalar Smash Hub con un toque.» y el botón.
  - **Comprobando:** Chromium (Chrome, Edge o Samsung Internet) fuera de iPhone, durante 6 s (`OFFER_WAIT_MS`) sin evento. Lleva `aria-busy`.
  - **Instalando:** la persona aceptó el diálogo y todavía no llegó `appinstalled`.
  - **Instalada:** por `appinstalled` («el navegador confirmó la instalación») o porque Chromium la detecta (`getInstalledRelatedApps`, «ya está instalada en este dispositivo»). Se ocultan las instrucciones y el botón pasa a «Seguir en el navegador».
  - **No disponible:** con un texto según el caso. Chrome o Edge todavía no lo ofrecen: usar el menú. Firefox u otros: pasos manuales. iPhone: Safari en tres pasos, o abrir en Safari. Navegador interno: ver más abajo. Cancelado: reintentar con los pasos.
  - **En uso:** dentro de la app instalada, solo «Ir al inicio».
- **Si el evento llega tarde**, el botón aparece igual: el estado es reactivo.
- **Navegadores internos** (WhatsApp, Instagram, Facebook, TikTok, la app de Google o cualquier WebView de Android): el panel lo explica y ofrece:
  - **Abrir en Chrome** (solo Android): un enlace `intent://` fijo hacia la URL pública de instalación, con la misma dirección `https` como alternativa si Chrome no está instalado. No lleva parámetros del usuario.
  - **Copiar enlace**, si el navegador permite usar el portapapeles.
  - Como última opción, «Abrir en el navegador» desde el menú de la app, o copiar la dirección a mano.
- **Detectar una instalación previa:** el manifest agrega `related_applications` (`platform: "webapp"`, la URL del propio manifest en el origen público) y `prefer_related_applications: false`. Al iniciar, la escucha global consulta `navigator.getInstalledRelatedApps()` cuando existe.
- **Pasos de Android:** se agregó qué hacer si se abrió desde la cámara o el lector de QR («Abrir en Chrome» en el menú), además de Samsung Internet y Firefox.

### Anuncio del inicio

- **Ubicación:** dentro de `section.home-intro`, como tercera columna a la derecha del título y la descripción y debajo de la navegación. El logo y el título no cambian. La franja de ancho completo entre la presentación y el ranking desapareció.
- **Tamaño:** `clamp(240px, 24vw, 280px)` de ancho. Medido: 280 px a 1280 de ancho y 246 px a 1024. Alto: 149 px.
- **Contenido:** ícono de celular y «Smash Hub en tu celular» en el título; QR de 68 × 68 px; «Instalá Smash Hub gratis.»; un botón compacto hacia `/install`. El texto del botón depende del dispositivo: «Instalar en Android», «Instalar en iPhone» o «Instalar en la PC».
- **Un solo mecanismo:** la tarjeta ya no abre el diálogo de instalación. Solo lleva a `/install`, que es el único lugar donde se instala.
- **Pantallas angostas:**
  - Hasta 860 px, la tarjeta pasa debajo del título, en la misma columna del texto.
  - Hasta 580 px, la presentación vuelve a una sola columna (el logo grande ya estaba oculto) y la tarjeta ocupa todo el ancho, hasta 360 px. El QR queda a la izquierda y el texto con el botón a la derecha.
  - Alto en el celular: 128 px. No hay desplazamiento horizontal a 320, 390, 768, 1024 ni 1280 px.
- **Se mantiene:** solo con sesión iniciada; oculta en modo standalone; oculta cuando el navegador confirma o detecta la instalación; el QR apunta a `https://smashclubpy.com/install` (o al origen configurado y validado) y no lleva tokens ni datos personales.

## 3. Diferencias respecto de SH-PWA-01

| Tema | SH-PWA-01 | SH-PWA-02 |
| --- | --- | --- |
| Anuncio del inicio | Franja de ancho completo entre la presentación y el ranking, QR de 76 px y «Instalar ahora», que abría el diálogo ahí mismo. | Tarjeta de 240–280 px a la derecha del título, QR de 68 px y botón hacia `/install`. |
| Botón en `/install` | Después del logo de 112 px y de las ventajas. | Primero, en un panel de estado. En el celular entra en la primera pantalla. |
| Estados | Instalando, instalada o cancelado. | Disponible, comprobando, instalando, instalada (evento o detectada), no disponible (con motivo) y en uso. |
| Navegadores internos | Instagram, Facebook, TikTok, Line y Twitter; solo un aviso. | Además WhatsApp, la app de Google, Snapchat y cualquier WebView de Android, con «Abrir en Chrome» y «Copiar enlace». |
| Instalación previa | No se detectaba. | `getInstalledRelatedApps` con `related_applications` en el manifest. |
| Detección del navegador | Plataforma y Safari de iOS. | Además, `detectBrowser` (Chrome, Edge, Samsung, Firefox, Safari, interno u otro) y `offersInstallDialog`. |

Sin cambios: la captura temprana de `beforeinstallprompt`, la escucha global, el manifest (el mismo archivo, solo con dos campos nuevos), los íconos, el layout, la autenticación y el backend.

## 4. Comportamiento esperado por plataforma

| Plataforma | Qué ve la persona en `/install` |
| --- | --- |
| Android, Chrome (o Edge / Samsung Internet) | «Comprobando…» unos instantes. Si Chrome ofrece instalar, aparece «Instalar Smash Hub» → diálogo nativo → «Instalando…» → «el navegador confirmó la instalación». Si a los 6 s no lo ofreció: menú ⋮ → Instalar aplicación. Si el evento llega después, el botón aparece igual. |
| Android, ya instalada | «Smash Hub ya está instalada en este dispositivo», sin instrucciones (si Chrome lo informa con `getInstalledRelatedApps`). |
| Android, desde WhatsApp, Instagram, Facebook o la app de Google | «Este navegador está dentro de otra app…», con «Abrir en Chrome» y «Copiar enlace». |
| Android, Firefox | Pasos manuales (menú ⋮ → Instalar), sin espera. |
| iPhone / iPad, Safari | «En iPhone se instala desde Safari, en tres pasos»: Compartir → Agregar a pantalla de inicio → Agregar. Nunca hay botón de instalación directa. |
| iPhone, otro navegador o navegador interno | Pide abrir la página en Safari. Sin enlace a Chrome. |
| Computadora, Chrome o Edge | Botón con el diálogo nativo cuando el navegador lo ofrece; si no, el ícono de la barra de direcciones o el menú. |
| Computadora, Safari (Mac) o Firefox | Pasos manuales: Archivo → Agregar al Dock, o usar otro navegador. |
| Dentro de la app instalada | «Ya estás usando Smash Hub instalada» e «Ir al inicio». |

En ninguna plataforma se instala sola: siempre hace falta que la persona toque el botón o use el menú del navegador.

## 5. Pruebas ejecutadas

| Verificación | Resultado |
| --- | --- |
| Vitest (suite web completa) | **171 aprobadas**, 35 archivos. `tests/pwa.test.tsx` pasa de 22 a 34 pruebas. En una corrida falló una vez `competitions.test.tsx` (sin cambios en esta misión). Pasó sola (9/9) y en dos corridas completas seguidas, así que es intermitente por carga. |
| `tsc --noEmit` | Sin errores. |
| `eslint --max-warnings 0` | Sin observaciones. |
| Prettier | Los archivos modificados están formateados. Los avisos restantes son finales de línea CRLF de archivos que esta rama no toca. |
| `next build` | Compila. `/manifest.webmanifest` sigue estático. |

**Pruebas nuevas o cambiadas:**
- **Detección:**
  - Chrome, Samsung Internet, Firefox y Edge.
  - Navegadores internos: Instagram y WebView de Android, WhatsApp, app de Google e Instagram de iOS.
  - Qué navegadores pueden mostrar el diálogo nativo.
  - El enlace `intent://` exacto.
- **Tarjeta del inicio:**
  - Contenido compacto, con un QR de 64 a 76 px hacia la URL pública y sin datos de la sesión.
  - Texto del botón por plataforma, siempre hacia `/install`.
  - No muestra un botón de instalación propio aunque haya evento.
  - Se oculta en modo standalone, con `appinstalled` y con `getInstalledRelatedApps`.
  - Ubicación: es el último hijo de `.home-intro`, junto al `h1`, y hay una sola tarjeta.
  - Reglas responsive: tres columnas, `clamp` de ancho, una columna en el celular y máximo de 360 px.
- **`/install`:**
  - El botón aparece antes de las ventajas.
  - Espera de 6 s (con temporizadores falsos), paso al menú, y el botón aparece si el evento llega tarde.
  - Firefox no espera.
  - iPhone en Safari, iPhone en otro navegador y navegadores internos de iOS sin enlace a Chrome.
  - WhatsApp e Instagram de Android con «Abrir en Chrome» y «Copiar enlace».
  - Instalando, instalada, cancelado, ya instalada detectada y en uso.
  - Conservación del evento capturado antes de hidratar.
- **Manifest:** `related_applications` y `prefer_related_applications`.

**Navegador real (Chrome headless sobre `next start`, sesión simulada):**

| Caso | Resultado |
| --- | --- |
| Inicio 1280 / 1024 | Tarjeta **a la derecha** del título (280 / 246 px), QR 68 × 68 con su nombre accesible, ranking debajo, sin desbordamiento. |
| Inicio 768 / 390 / 320 | Tarjeta **debajo** del título (240 / 358 / 288 px de ancho, 128–149 px de alto), sin desbordamiento. |
| Inicio sin sesión | Sin tarjeta. |
| `/install` con evento | Botón visible en la primera pantalla a 390 × 844, 360 × 640, 320 × 568 y 1280 × 900. |
| Inicio → tarjeta → `/install` | Llega a `/install` con el botón disponible (el evento se conserva). |
| `/install` sin evento (bloqueado), Android | A los 8 s: «El navegador todavía no ofrece la instalación directa…», con los pasos del menú. |
| `/install`, iPhone (sin evento) | «En iPhone se instala desde Safari, en tres pasos.» |
| `/install`, WhatsApp de Android (sin evento) | Mensaje de navegador interno y «Abrir en Chrome» con el `intent://` correcto. |
| Standalone (`navigator.standalone`) | Inicio sin tarjeta. `/install`: «Ya estás usando Smash Hub instalada.» |
| Rutas | `/`, `/prode`, `/logros`, `/logros/oracle`, `/players`, `/rankings`, `/cuenta`, `/ingresar`, `/install` y `/manifest.webmanifest` responden 200. |

**No hubo pruebas en dispositivos físicos.** No se probó en Android, iPhone ni iPad reales. Los casos de iPhone y WhatsApp se simularon cambiando el user agent y bloqueando el evento, porque Chrome de escritorio sí lo dispara. Chrome headless acepta la emulación de `display-mode` pero no la aplica, así que el modo standalone se probó con `navigator.standalone`.

## 6. Limitaciones del navegador

- **Chrome decide** si manda `beforeinstallprompt` y cuándo. Puede pedir interacción previa con el sitio, no lo repite si la app ya está instalada o si la persona lo rechazó hace poco, y no lo manda en Custom Tabs ni en WebView. En esos casos queda el menú ⋮.
- **Instalación automática:** ningún navegador permite instalar sin un toque de la persona. La página no lo intenta.
- **`getInstalledRelatedApps`:** solo existe en Chromium (Android y computadora) y solo informa la instalación hecha desde el mismo origen. Si alguien instaló desde `*.ondigitalocean.app`, no se detecta desde `smashclubpy.com`.
- **«Abrir en Chrome»** usa un `intent://` de Android. Algunas apps (sobre todo Instagram y Facebook) pueden bloquearlo. Por eso también están «Copiar enlace» y la indicación del menú de la app.
- **Custom Tabs** (la pestaña que abren algunas apps y lectores de QR) usa el mismo user agent que Chrome y no se puede distinguir. Se ve como Chrome: «Comprobando…» y después las instrucciones, que explican el paso «Abrir en Chrome».
- **iPhone:** solo Safari, sin evento y sin `appinstalled`. Nunca se afirma la instalación. La app instalada guarda su propia sesión.
- **Espera de 6 s:** es un criterio de presentación. Si Chrome manda el evento después, el botón aparece igual.

## 7. Archivos modificados

- `apps/web/src/lib/install.ts`:
  - `publicOrigin`, `openInChromeUrl`, `detectBrowser` y `offersInstallDialog`.
  - `isInAppBrowser` reconoce WhatsApp, la app de Google, Snapchat, `FB_IAB` y WebView.
- `apps/web/src/lib/pwa.ts`: `installed` pasa a ser `"event" | "detected" | null`, y se agregó la detección con `getInstalledRelatedApps`.
- `apps/web/src/components/pwa.tsx`:
  - Tarjeta compacta, que solo enlaza a `/install`.
  - `/install` reorganizada en torno a `useInstallPhase`, con `OFFER_WAIT_MS` y `CopyLink`.
- `apps/web/src/app/page.tsx`: la tarjeta pasa a `section.home-intro`.
- `apps/web/src/app/manifest.ts`: `related_applications` y `prefer_related_applications`.
- `apps/web/src/app/globals.css`: estilos de la tarjeta, la columna del encabezado y el panel de `/install`, con sus reglas responsive.
- `apps/web/tests/pwa.test.tsx`: 34 pruebas.
- `docs/operations/sh-pwa-02.md` (este archivo), [sh-pwa-01.md](sh-pwa-01.md) (referencia) y `README.md`.

Sin dependencias nuevas, sin service worker y sin cambios en la API, la base, las migraciones, la autenticación, el Prode, los logros, los rankings ni los perfiles.

## 8. Publicación (requiere autorización)

Solo cambia el servicio `web`, sin variables nuevas.

1. **Integrar y hacer push:** con autorización, integrar `sh-pwa-02` en `main` (avance rápido si `main` no cambió) y hacer push. No hay `deploy_on_push`.
2. **Desplegar** solo el servicio `web` desde el panel de DigitalOcean. El token de `doctl` disponible responde 403 en Apps ([sh-pwa-01, 8.3](sh-pwa-01.md#83-despliegue-detenido-por-falta-de-permisos)).
3. **Verificar en producción:**
   - `GET /manifest.webmanifest`: 200, con `related_applications`.
   - `GET /install`: 200.
   - En Chrome, `/install`: sin errores de instalabilidad y con el botón en la primera pantalla.
   - Inicio con sesión: la tarjeta queda a la derecha del título en la computadora y debajo en el celular, sin la franja anterior.
   - `/prode`, `/logros` y los perfiles responden igual que antes.
4. **Probar en dispositivos reales:**
   - **Android con Chrome:** escanear el QR con la cámara y con Google Lens. Ver si abre en Chrome o en una pestaña de otra app, si aparece el botón, y que el diálogo nativo instale la app.
   - **Android desde WhatsApp:** abrir el enlace desde un chat y probar «Abrir en Chrome».
   - **Android con la app ya instalada:** abrir `/install` en Chrome y confirmar que diga «ya está instalada».
   - **iPhone con Safari:** seguir los tres pasos.
5. Recién después, anunciar.

**Reversión:** redesplegar en `web` el commit anterior (`9e07727`, SH-PWA-01). No hay datos ni migraciones. Quien ya instaló la app conserva el ícono.

## 9. Publicación: resultados reales

Publicación autorizada el 12/11/2026. No se tocaron backend, API, PostgreSQL, migraciones ni variables de entorno.

### 9.1 Verificaciones previas (12/11/2026, ~21:50 UTC)

| Verificación | Resultado |
| --- | --- |
| Rama vs `main` | `origin/main` = `9e07727` (SH-PWA-01) es ancestro de `sh-pwa-02`. No hay commits en el remoto que falten en la rama. La integración es un avance rápido y no se pierde nada. |
| Producción antes de publicar | Corre SH-PWA-01: `/install` y `/manifest.webmanifest` responden 200, y el manifest **no** tiene `related_applications`. |
| Línea base | Catálogo de logros: 109. Prode de Center Stage: `open`, 8 participantes, `locks_at = 2026-11-14T19:00:00+00:00`, sin liquidar. Responden 200: `/`, `/install`, `/prode`, `/logros`, `/logros/oracle`, `/rankings`, `/players`, `/players/{id}`, `/ingresar`, `/cuenta`, `/api/v1/health/ready` y `/api/v1/achievements/players/{id}`. |

### 9.2 Integración y push

- `sh-pwa-02` se integró en `main` por avance rápido y se hizo push: `origin/main` pasó de `9e07727` a **`366e566`**.
- Commits: `ccf8aaa` (código) y `366e566` (documentación). Después se suma el commit de esta sección, que solo cambia la documentación.
- **Commit a desplegar en `web`:** `366e566` o posterior. El código de la aplicación es el de `ccf8aaa`.

### 9.3 Despliegue: detenido por falta de permisos

- `doctl --context smashhub apps list` respondió **403 Forbidden**. Siguiendo la instrucción, no se insistió ni se cambiaron credenciales.
- El push no desplegó (no hay `deploy_on_push`). A las 21:58 UTC el manifest de producción seguía sin `related_applications`: el servicio `web` corre SH-PWA-01.
- Ninguna de las verificaciones posteriores al despliegue se pudo hacer.

### 9.4 Para completar a mano

1. En el panel de DigitalOcean, app `smash-hub-app`, desplegar **solo el servicio `web`** desde `main` (`366e566` o posterior). Sin cambios en el spec ni en las variables. No tocar `api` ni `migrate`.
2. Avisar para verificar desde aquí, contra la línea base de 9.1:
   - `/manifest.webmanifest` con `related_applications` (confirma que el despliegue tomó el código nuevo) y `/install`: 200.
   - En Chrome (DevTools Protocol), `/install`: sin errores de instalabilidad y con «Instalar Smash Hub» en la primera pantalla cuando Chrome manda el evento.
   - El QR de la tarjeta apunta a `https://smashclubpy.com/install`.
   - Con sesión: tarjeta a la derecha del título en la computadora (1280 / 1024) y debajo en el celular (390 / 320), sin desbordamiento.
   - Modo standalone: sin tarjeta, y `/install` dice «Ya estás usando Smash Hub instalada».
   - Prode (mismo estado, `locks_at` y participantes), logros (109), rankings, perfiles y `/ingresar` sin cambios.
3. Pruebas en dispositivos físicos (sección 8, paso 4). **Hasta hacerlas, la instalación no está probada en Android ni en iPhone reales.**

**Reversión:** redesplegar `web` en `9e07727` (SH-PWA-01).
