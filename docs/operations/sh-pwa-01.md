# SH-PWA-01 — Smash Hub como aplicación instalable

Fecha: 12/11/2026. Estado: **implementado y probado en local, sin publicar.** Falta autorización para hacer push a `main` y desplegar ([sección 7](#7-publicación-requiere-autorización)).

Smash Hub se puede instalar como Progressive Web App (PWA) en Android, iPhone, iPad y computadoras. Es la misma aplicación Next.js: no hay APK, app nativa ni un frontend aparte.

## 1. Qué se implementó

| Bloque | Contenido |
| --- | --- |
| Manifest | `src/app/manifest.ts`, con la convención de Next.js. Se sirve estático en `/manifest.webmanifest` (`application/manifest+json`), y Next agrega `<link rel="manifest">` en todas las páginas. Valores: `id` `/`, `name` y `short_name` «Smash Hub», `start_url` `/`, `scope` `/`, `display` `standalone`, `lang` `es` y `background_color`/`theme_color` `#26221f` (el gris `--concrete` del diseño, que también es el fondo del logo). No lleva parámetros ni datos del usuario. |
| Íconos | `public/icons/`: `icon-192.png`, `icon-512.png`, `icon-maskable-512.png` y `apple-touch-icon.png` (180 × 180). Salen del logo oficial (`public/smashclublogo.jpg`) con `scripts/generate-pwa-icons.mjs` (sharp, que ya estaba instalado). El maskable reduce el logo al 90 % y completa el margen reflejando la textura del propio fondo, así el emblema queda dentro de la zona segura sin agregar arte nuevo. |
| Metadata | `src/app/layout.tsx`: `viewport` con `themeColor` y `viewport-fit=cover`; `applicationName` y `appleWebApp` (`capable`, título «Smash Hub», barra de estado `black`); Apple Touch Icon nuevo. El favicon y las imágenes de vista previa no cambian. |
| Escucha global | `InstallListener`, montado en el layout, registra `beforeinstallprompt` y `appinstalled` para toda la app. Además, un script en línea en `<head>` (`next/script`, `beforeInteractive`) guarda el evento si Chromium lo dispara antes de que React hidrate. Así no se pierde aunque la persona llegue a `/install` desde otra página. |
| Bloque en el inicio | `HomeInstallCard`: «Smash Hub en tu celular», con ícono de celular, QR de 76 × 76 px, enlace según el dispositivo y la aclaración de que no hace falta descargar un APK. Solo para usuarios con sesión. No aparece dentro de la app instalada ni cuando el navegador confirma la instalación. Si el navegador ofrece instalar, muestra «Instalar ahora», que abre el diálogo directamente. |
| Página `/install` | Pública y sin parámetros. Muestra el logo, el nombre, las ventajas, el botón «Instalar Smash Hub» (solo si el navegador ofrece instalar), «Entrar sin instalar» (a `/`) y las instrucciones para Android, iPhone/iPad y computadora. El dispositivo detectado aparece primero y desplegado; los otros quedan a un toque. |
| Lógica | `src/lib/install.ts` (funciones puras: origen público, URL del QR, plataforma, navegador, standalone y el script en línea) y `src/lib/pwa.ts` (estado de la oferta de instalación y hooks). |

### Archivos

- **Nuevos:** `apps/web/src/app/manifest.ts`, `src/app/install/page.tsx`, `src/components/pwa.tsx`, `src/lib/install.ts`, `src/lib/pwa.ts`, `public/icons/*.png` (4), `scripts/generate-pwa-icons.mjs` y `tests/pwa.test.tsx`.
- **Modificados:** `src/app/layout.tsx`, `src/app/page.tsx`, `src/app/globals.css` (estilos del bloque y la página, más las áreas seguras), `package.json` y `package-lock.json` (`qrcode.react` 4.2.0, versión fija).

### Comportamiento de la instalación

- **QR:** codifica `https://smashclubpy.com/install`. Si se configura `NEXT_PUBLIC_SITE_URL`, usa ese origen, pero solo si es un origen limpio: `https`, sin usuario ni contraseña, sin ruta, sin `?` ni `#` (se acepta `http` solo para `localhost`). Cualquier otro valor se descarta y se vuelve al dominio por defecto. No toma el host de la petición, que se puede falsificar con encabezados.
- **Android y computadora (Chrome, Edge, Samsung Internet):** se intercepta `beforeinstallprompt` para usar el botón propio en lugar del aviso del navegador. Cada oferta se usa una sola vez: después de mostrar el diálogo, el botón desaparece hasta que el navegador mande otra.
- **Confirmación:** «Aceptar» en el diálogo solo muestra «Instalando…». La página dice que la app quedó instalada recién al recibir `appinstalled`.
- **Sin `beforeinstallprompt`** (Firefox, Safari, navegadores dentro de otras apps o cuando Chrome no lo ofrece todavía): se muestran solo las instrucciones manuales.
- **iPhone/iPad:** instrucciones de Safari (Compartir → Agregar a pantalla de inicio → Agregar). En otro navegador de iOS se pide abrir la página en Safari. iPadOS se detecta aunque se presente como Mac, por la pantalla táctil.
- **Navegadores dentro de Instagram, Facebook, TikTok, etc.:** un aviso pide abrir la dirección en Chrome o Safari.
- **Standalone:** se detecta con `display-mode` (`standalone`, `fullscreen`, `minimal-ui`) o `navigator.standalone` en iOS. Dentro de la app, `/install` solo ofrece «Ir al inicio».

### Autenticación, navegación y seguridad

- **Sesión y permisos:** no cambian las cookies, la sesión ni los permisos. La app instalada abre `/`. Sin sesión, «Ingresar» lleva al flujo de login de siempre (`/ingresar`), que está dentro del `scope` y por eso queda dentro de la app. La API está en el mismo dominio (`/api/v1`), así que la cookie HttpOnly funciona igual.
- **Volver al inicio:** el logo del encabezado lleva a `/` en todas las páginas, también en modo standalone (iOS no tiene botón atrás).
- **Áreas seguras:** con `viewport-fit=cover`, el `body` aplica `env(safe-area-inset-*)`. En una pestaña normal los valores son 0, así que solo actúa en la app instalada (muesca, esquinas, indicador de inicio). La barra de estado de iOS es `black`: el contenido empieza debajo de ella.
- **Seguridad:** el QR y la página no llevan tokens, sesiones ni parámetros. `/install` no acepta redirecciones. El manifest es estático. No se guarda nada nuevo en el navegador. **No hay service worker**: no hay caché ni modo sin conexión. Los enlaces externos (start.gg, etc.) se abren en el navegador, como corresponde fuera del `scope`.

## 2. Interfaz

- **Inicio con sesión, en computadora:** una franja entre la presentación y el ranking, con borde naranja a la izquierda. Ícono de celular, título «Smash Hub en tu celular», texto, botón naranja («Instalar ahora» o el enlace del dispositivo) y, a la derecha, el QR con «Escaneá con el celular».
- **Inicio con sesión, en celular:** el mismo bloque en una columna; el QR pasa abajo con su leyenda al lado. Sin desplazamiento horizontal a 390 px.
- **`/install` en celular:** logo, «Smash Hub», bajada, cuatro ventajas con viñetas naranjas inclinadas, botones a todo el ancho (48 px de alto) y las guías por plataforma como secciones desplegables.

## 3. Pruebas

| Verificación | Resultado |
| --- | --- |
| Vitest (suite web completa) | **159 aprobadas**, 35 archivos. Nuevas: 22 en `tests/pwa.test.tsx`. |
| `tsc --noEmit` | Sin errores. |
| `eslint --max-warnings 0` | Sin observaciones. |
| Prettier | Los archivos nuevos y modificados están formateados. |
| `next build` | Compila. `/manifest.webmanifest` sale estático y `/install` está incluida. |
| Chrome real (headless, por DevTools Protocol, sobre `next start`) | `Page.getInstallabilityErrors`: **ninguno**. `Page.getAppManifest`: sin errores. Chrome disparó `beforeinstallprompt` y apareció el botón «Instalar Smash Hub». `/install` en Android, iPhone y escritorio ordena y despliega la guía correcta. Inicio sin sesión: sin bloque. Con sesión simulada: bloque visible, QR de 76 × 76 que apunta a `https://smashclubpy.com/install`, sin desplazamiento horizontal. Con `navigator.standalone`: el bloque se oculta y `/install` muestra «Ya estás usando Smash Hub instalada». |

**Qué cubren las pruebas nuevas:**
- **Manifest y metadata:** campos obligatorios, sin parámetros ni datos personales, íconos con el tamaño declarado (se lee el PNG), `viewport`, `appleWebApp` y Apple Touch Icon en el layout.
- **QR y URL pública:** dominio por defecto, origen configurado y rechazo de `http`, credenciales, rutas, `?next=`, `#` y valores no válidos.
- **Detección de dispositivo:** iPhone, iPad (como Mac táctil), Android y computadora; Safari frente a Chrome de iOS y navegadores dentro de otras apps.
- **Standalone:** por `display-mode` y por `navigator.standalone`; el bloque se oculta y la página cambia.
- **Instalación:** `preventDefault` sobre la oferta, un solo uso, «Instalando…» sin afirmar el éxito hasta `appinstalled`, cancelación y conservación del evento capturado antes de hidratar.
- **Fallback:** sin `beforeinstallprompt` no hay botón y se muestran las instrucciones.
- **Accesibilidad básica:** región con nombre, encabezados, QR con `role="img"` y nombre accesible, botones y enlaces con nombre, estado en `role="status"` y guías con `<details>`/`<summary>` operables con teclado.

**No se probó en dispositivos físicos** (Android, iPhone ni iPad). La instalación en iOS no se puede verificar desde Windows. Chrome headless acepta la emulación de `display-mode` pero no la aplica, así que el modo standalone se verificó con `navigator.standalone`.

## 4. Limitaciones por navegador

| Plataforma | Comportamiento |
| --- | --- |
| Chrome / Edge / Samsung Internet (Android) | Botón de instalación propio cuando el navegador lo ofrece. Chrome lo ofrece según sus propias reglas de interacción, así que puede no aparecer en la primera visita; entonces se muestran las instrucciones del menú. Al interceptar el evento ya no aparece el aviso automático del navegador. |
| Chrome / Edge (computadora) | Igual que Android. También queda el ícono de instalar en la barra de direcciones. |
| Safari (iPhone/iPad) | No hay instalación programática. Solo instrucciones: Compartir → Agregar a pantalla de inicio. La app instalada tiene **sus propias cookies**: hay que iniciar sesión otra vez dentro de ella. La página lo avisa. |
| Chrome, Firefox y otros en iOS | Desde iOS 16.4 algunos permiten agregar a inicio, pero no es uniforme: se indica usar Safari. |
| Safari (Mac) | Archivo → Agregar al Dock (macOS 14 o posterior). Sin evento de instalación. |
| Firefox (computadora) | No instala sitios. Se indica usar otro navegador. Firefox Android sí ofrece «Instalar» desde su menú. |
| Navegadores dentro de otras apps | No instalan. Se avisa que hay que abrir la página en Chrome o Safari. |
| Todas | `appinstalled` no existe en Safari: allí nunca se afirma la instalación. Si la persona desinstala la app, el bloque vuelve a aparecer en el navegador. |

## 5. Problemas conocidos

1. **Nombre:** el manifest y el ícono instalado dicen «Smash Hub», como pide la misión, pero el sitio sigue titulado «Smash Club Paraguay» (encabezado, `<title>` y vistas previas). Si se quiere unificar, es una decisión de marca aparte.
2. **Dominio del QR:** apunta a `https://smashclubpy.com/install`. Ese dominio tiene que resolver a la app de App Platform con HTTPS antes de anunciar el bloque; si no, el QR lleva a una página que no existe. Mientras tanto se puede fijar `NEXT_PUBLIC_SITE_URL` con el dominio que funcione.
3. **Sin pruebas en dispositivos físicos** (sección 3).
4. **Sin funcionamiento offline:** sin conexión, la app instalada muestra el error del navegador. Es una decisión de esta primera versión.
5. **Origen de la instalación:** si alguien instala desde `*.ondigitalocean.app` y otra persona desde `smashclubpy.com`, son dos apps distintas para el navegador (el `id` se resuelve con el origen).

## 6. Regenerar los íconos

Si cambia el logo (`apps/web/public/smashclublogo.jpg`), desde `apps/web`:

```powershell
node scripts/generate-pwa-icons.mjs
```

Revisar `public/icons/icon-maskable-512.png` (el emblema tiene que entrar en el círculo central del 80 %) y hacer commit de los PNG.

## 7. Publicación (requiere autorización)

No hay migraciones ni cambios en la API. Solo cambia el servicio `web`.

1. **Revisión y push:** con autorización, integrar en `main` y hacer push. No hay `deploy_on_push`.
2. **Dominio:** confirmar que `https://smashclubpy.com` apunta a la app con certificado válido. Si todavía no, en el spec de `web` agregar `NEXT_PUBLIC_SITE_URL` (`RUN_AND_BUILD_TIME`) con el origen público real, sin ruta ni barra final. Es pública y se fija durante la compilación, igual que `NEXT_PUBLIC_API_URL`.
3. **Desplegar** el servicio `web` (`npm ci && npm run build`, instala `qrcode.react`).
4. **Verificar:**
   - `GET /manifest.webmanifest` → 200, `application/manifest+json`, `"name":"Smash Hub"`.
   - `GET /icons/icon-192.png`, `/icons/icon-512.png`, `/icons/icon-maskable-512.png` y `/icons/apple-touch-icon.png` → 200.
   - `GET /install` → 200.
   - En Chrome de computadora: DevTools → Application → Manifest, sin errores ni advertencias de instalabilidad.
   - Con sesión, el inicio muestra «Smash Hub en tu celular» y el QR abre `/install` al escanearlo.
5. **Prueba en dispositivos:**
   - **Android (Chrome):** instalar desde `/install`. El ícono aparece en el inicio, abre `/` a pantalla completa, el login funciona y el bloque del inicio ya no aparece.
   - **iPhone (Safari):** agregar a inicio. Abre a pantalla completa, sin contenido tapado por la muesca, y se puede iniciar sesión (probablemente pida ingresar de nuevo).
6. **Volver atrás:** redesplegar el commit anterior del servicio `web`. No hay datos ni migraciones que revertir. Quien ya la instaló conserva el ícono, que abre el sitio normal.
