# SH-OBS-01 — Overlays profesionales para OBS

Fecha: 13/11/2026. Paquete: [stream-assets/obs-overlays/](../../stream-assets/obs-overlays/README.md). Primera versión para revisión estética; no se hizo push ni despliegue. La ampliación con bracket y la identidad oficial de Center Stage está en la [sección 10](#10-ampliación-bracket-y-center-stage-con-identidad-oficial).

## 1. Qué se entregó

Seis escenas locales (HTML, CSS, imágenes y fuentes) para la fuente de navegador de OBS, a 1920 × 1080, sin internet, sin backend y sin instalar nada.

| Escena | Archivo | Fondo | Contenido |
| --- | --- | --- | --- |
| Gameplay | `gameplay.html` | Transparente | Marcador (nombres, prefijos, puntos, ronda), pestaña con formato y evento, marca abajo a la izquierda, patrocinadores rotando abajo a la derecha |
| Versus | `versus.html` | Opaco | Ronda, jugadores con prefijo y personaje opcional, VS central, fecha y lugar, logo del club y del evento, tira de patrocinadores |
| Empezamos pronto | `starting-soon.html` | Opaco | Logo con anillos y luz, título, evento, fecha, hora, lugar, cuenta regresiva opcional, redes, sitio y patrocinadores |
| Volvemos enseguida | `intermission.html` | Opaco | Título con símbolo de pausa, próximo set, patrocinadores y cinta de mensajes |
| Comentaristas | `commentators.html` | Opaco con dos huecos transparentes | Dos cámaras 16:9 (860 × 484), nombres y usuarios, título, patrocinadores |
| Patrocinadores | `sponsors.html` | Opaco | Agradecimiento, principal destacado, cuatro secundarios, redes y sitio |

Además: `README.md` con instrucciones para OBS, capturas en `previews/`, dos vistas previas con gameplay y cámaras simuladas, la variante Center Stage y el ZIP.

## 2. Identidad: de dónde sale cada decisión

Se analizaron `apps/web/src/app/globals.css`, `layout.tsx`, el logo y las imágenes OG del sitio.

| Del sitio | En los overlays |
| --- | --- |
| Paleta tomada del logo: concreto `#26221f`, losa `#302b27`, hueso `#efe9df`, ceniza `#a2988d`, fuego `#e5541b`, oro `#f3a81f` | Mismos valores, como variables en `assets/css/base.css`. El fondo de escena baja a `#120f0d` para dar más contraste en video |
| «Fuego para la acción, oro solo para el líder» | Fuego en acentos y marcadores; oro solo para quien gana el set, la cuenta regresiva y el VS |
| Big Shoulders Display (títulos) y Atkinson Hyperlegible (texto) | Las mismas, incluidas localmente (OFL) |
| Números de posición inclinados `skewX(-10/-12deg)` | La inclinación de -12° es el lenguaje de todo el paquete: placas, puntos, títulos, costura del versus, losas, pausa |
| «Sin degradados ni brillos» en el sitio | Adaptado a transmisión: luz cálida tenue, textura de concreto, brasas sutiles y brillo solo en elementos clave |
| Logo `smashclublogo.jpg` | Sin modificar. Se generó un recorte circular con borde suave (`smash-club-paraguay-circular.png`) para que no se vea el cuadrado de fondo. El original también está incluido |
| Íconos de personajes de `public/characters/` | Los mismos SVG, para el personaje opcional del versus |

Otras decisiones:
- **Legibilidad en celular:** nombres del gameplay a 40 px como mínimo en Big Shoulders 800, puntos a 52 px y alto contraste (hueso sobre casi negro, oscuro sobre fuego).
- **Lados del set:** cada jugador tiene una franja de color (fuego para el 1, hueso para el 2) en lugar de rojo y azul, para no salir de la paleta.
- **Cada escena tiene su composición:** versus dividido en diagonal, «Empezamos pronto» con emblema y título, «Volvemos enseguida» con mensaje y tarjeta lateral, patrocinadores con agradecimiento y vitrina.

## 3. El gameplay y el HUD de Smash Ultimate

Zonas que se dejan libres (1 vs 1, 1920 × 1080):

- franja inferior central, x 480–1440, y > 880: porcentajes, retratos y stocks;
- esquina superior derecha, x > 1620, y < 120: temporizador.

El marcador ocupa x 391–1529, y 22–118; la marca, x 40–470 abajo a la izquierda; los patrocinadores, x 1580–1880 abajo a la derecha. Se comprobó en `previews/01-gameplay-zonas-hud.png`, que marca las zonas en rojo sobre un HUD simulado.

**Las posiciones del HUD son aproximadas.** El escenario y el HUD de la vista previa están dibujados con CSS (no se usó ninguna captura del juego). Antes del primer torneo conviene comprobarlo con una captura real de la consola.

## 4. Cómo se edita

Todo está en `stream-assets/obs-overlays/config/`:

- `partida.js`: ronda, formato, jugadores, prefijos, personajes, marcadores, próximo set y qué esquinas del gameplay se muestran.
- `evento.js`: tema, evento, fecha, hora, lugar, cuenta regresiva, sitio, redes, logos, patrocinadores, comentaristas, textos de pantallas y mensajes de la cinta.

Las escenas releen estos archivos **cada 2 segundos** (los vuelven a cargar como `<script>`, que funciona con `file://`), así que no hace falta refrescar OBS. Solo se vuelve a dibujar si algo cambió, así que no se reinician las animaciones. También se pueden pasar datos por URL (`?p1=…&s1=…`), con prioridad sobre `config/`. No hay panel de control.

Los nombres largos se achican solos hasta entrar en su caja (mínimo entre el 45 % y el 70 % del tamaño, según el lugar). Probado con «Supercalifragilístico» y «Mbarete Guasu Paraguay» (`previews/01-gameplay-nombres-largos.png`).

## 5. Center Stage

> **Actualizado:** los colores provisionales y el placeholder de esta sección se reemplazaron por la identidad oficial; ver la [sección 10](#10-ampliación-bracket-y-center-stage-con-identidad-oficial).

- `assets/css/temas/center-stage.css` redefine las variables de color. Se activa con `tema: "center-stage"` en `evento.js`.
- **Los colores que trae son provisionales** (un turquesa), solo para comprobar que la variante funciona. No son la identidad del torneo.
- El logo oficial va en `assets/images/eventos/center-stage/logo.png` y se indica en `logoEvento`. Hoy hay un placeholder que dice «Logo oficial pendiente».
- Con logo de evento, el del torneo reemplaza al del club en las escenas que muestran uno solo; el versus muestra los dos.
- No se inventó el logo de Center Stage ni el de ningún patrocinador. Los patrocinadores son placeholders con borde punteado y la palabra «PLACEHOLDER».

## 6. Archivos creados

```
stream-assets/obs-overlays/
  gameplay.html  versus.html  starting-soon.html  intermission.html  commentators.html  sponsors.html
  README.md
  config/evento.js  config/partida.js
  assets/css/base.css  gameplay.css  versus.css  starting-soon.css  intermission.css  commentators.css  sponsors.css
  assets/css/temas/center-stage.css
  assets/js/overlay.js
  assets/fonts/  big-shoulders-display.woff2  atkinson-hyperlegible-400.woff2  atkinson-hyperlegible-700.woff2  OFL-*.txt
  assets/images/marca/  smash-club-paraguay.jpg (copia del logo)  smash-club-paraguay-circular.png
  assets/images/personajes/  84 SVG (copia de apps/web/public/characters/)
  assets/images/patrocinadores/  placeholder-principal.svg  placeholder-1..4.svg
  assets/images/eventos/center-stage/logo-placeholder.svg
  previews/  15 PNG  gameplay-simulado.html  commentators-simulado.html
  herramientas/capturar.py
.gitignore: se agrega stream-assets/dist/
```

ZIP: `stream-assets/dist/smash-hub-obs-overlays.zip` (21 MB, 133 archivos). No se versiona; se regenera desde la carpeta.

No se modificó nada de `apps/`, la API, la base, las migraciones, las rutas, el Prode ni el frontend público.

## 7. Pruebas realizadas

Con Chrome 157 y Playwright, a 1920 × 1080, abriendo los archivos con `file://` desde una ruta con espacios (`herramientas/capturar.py`):

| Prueba | Resultado |
| --- | --- |
| Las seis escenas cargan y se dibujan | Sí, 15 capturas sin errores de JavaScript |
| Recursos externos | Ninguno: la herramienta registra cualquier pedido que no sea `file:` o `data:` y no hubo. Tampoco hay URLs `http` en HTML, CSS ni JS |
| Recursos locales que no cargan | Ninguno |
| Gameplay transparente | Sí: los píxeles fuera del marcador tienen alfa 0 (`01-gameplay.png`) |
| Huecos de cámara transparentes | Sí: alfa 0 dentro de los dos huecos, opaco fuera (`05-commentators.png`) |
| HUD libre | Sí, sobre el HUD simulado (`01-gameplay-zonas-hud.png`) |
| Nombres largos | Se achican sin cortarse ni salir de la placa |
| Ganador del set | Con 3 en BO5, el punto pasa a oro |
| Sin personajes | El versus muestra la inicial gigante en contorno y deja los nombres a la misma altura |
| Cuenta regresiva | Aparece con `inicio` y se oculta si está vacío |
| Variante Center Stage | Cambia paleta, luces, brasas y logo sin tocar las escenas |

Problemas encontrados en la revisión visual y corregidos: título de «Empezamos pronto» desbordado, acentos de «Ñ» e «Í» recortados, nombres del versus achicados por altura, marcos de personaje desalineados con un solo prefijo, costura del versus cruzando el título, logo principal invisible en patrocinadores por un choque de clases, texto de los placeholders desbordado y cámaras chicas en comentaristas.

### Capturas

| Archivo | Qué muestra |
| --- | --- |
| `01-gameplay.png` | Overlay transparente original |
| `01-gameplay-simulado.png` | Sobre gameplay y HUD simulados (vista previa) |
| `01-gameplay-zonas-hud.png` | Ídem, con las zonas del HUD marcadas |
| `01-gameplay-nombres-largos.png` | Nombres y prefijo largos, set ganado |
| `02-versus.png`, `02-versus-sin-personajes.png` | Con y sin personajes |
| `03-starting-soon.png`, `03-starting-soon-sin-cuenta.png` | Con y sin cuenta regresiva |
| `04-intermission.png` | Volvemos enseguida |
| `05-commentators.png` | Overlay original con huecos transparentes |
| `05-commentators-simulado.png` | Con cámaras simuladas debajo (vista previa) |
| `06-sponsors.png` | Patrocinadores |
| `07-center-stage-*.png` | Variante Center Stage (versus, gameplay, empezamos pronto) |

Las vistas previas `*-simulado` son solo para revisar: no son overlays y no se cargan en OBS.

## 8. Limitaciones

1. **No se probó dentro de OBS.** Se probó en Chrome 157. Se requiere OBS 31 o posterior (Chromium 127): las escenas usan `color-mix()`, máscaras y las propiedades `translate` y `rotate`, que versiones anteriores no soportan del todo.
2. **HUD aproximado**: falta comprobar las zonas con una captura real de Smash Ultimate. Solo se contempló 1 vs 1; dobles (4 HUD) tapan más de la franja inferior.
3. **Placeholders**: patrocinadores, redes, sitio web y comentaristas son ejemplos marcados con `REEMPLAZAR`. Center Stage no tiene logo ni colores oficiales.
4. **Personajes**: son los íconos chicos del sitio. En el versus quedan bien en el marco, pero el fondo ampliado es de baja definición a propósito (apagado y en gris). Para mejor impacto se podrían usar renders de mayor resolución, con licencia verificada.
5. **Logos de patrocinadores**: en el gameplay el espacio es de 228 × 48 px; logos muy horizontales o con mucho margen se van a ver chicos.
6. **Edición manual**: el marcador se cambia editando `config/partida.js`, como se pidió (sin panel ni start.gg).
7. **Tamaño**: las capturas pesan unos 2 MB cada una por la textura de concreto; el paquete completo, 21 MB.
8. **Rendimiento**: las brasas y la cinta animadas son livianas (CSS), pero no se midió el consumo dentro de OBS en una PC de transmisión.

## 9. Próximos pasos sugeridos

1. Revisión estética de las capturas: colores, distribución, tamaños.
2. Cargar las seis escenas en OBS 31+ con una captura real de la consola y ajustar las zonas del HUD si hace falta.
3. Recibir logos y colores oficiales de Center Stage y de sus patrocinadores, y reemplazar placeholders.
4. Completar redes, sitio y comentaristas reales en `config/evento.js`.

## 10. Ampliación: bracket y Center Stage con identidad oficial

Pedido del 13/11/2026: agregar el bracket y mejorar la variante Center Stage con el pack oficial `CENTER-STAGE-OBS-PACK.zip` (logos, 11 auspiciantes, 3 videos de referencia y una versión anterior de overlays con panel y servidor local).

### 10.1 Qué se tomó del pack y qué no

| Del pack | Uso |
| --- | --- |
| `center-stage.jpg`, `center-stage-horizontal.jpg` | Se quitó solo el fondo negro (transparencia según el brillo de cada píxel; el dibujo no cambia) → `logo.png` y `logo-horizontal.png`. Los JPEG originales quedan en `eventos/center-stage/originales/` |
| `sponsors/1–11.png` | Copiados a `patrocinadores/center-stage/`, reducidos a 800 × 400 como máximo (el 9 medía 3583 px) |
| Paleta del LEEME: fucsia `#E32C64`, violeta `#30244A`, negro `#08070C`, blanco `#F8F5FB` | Variables de `temas/center-stage.css`; reemplazan los colores provisionales |
| Videos `inicio`, `pausa`, `top-8` | Referencia visual: cuadrícula fucsia sobre negro, cruces «X» y triángulos, palabra rellena en fucsia + palabra en contorno blanco, rótulos en caja fucsia, banda «Auspician» |
| Panel `panel.html`, `servidor.py`, `INICIAR-PANEL.bat` | **No se usaron**: la consigna de SH-OBS-01 excluye paneles y servidores |
| Videos MP4 | No se incluyen en el paquete (no hacen falta para los HTML) |

El ZIP del pack quedó en `stream-assets/obs-overlays/` y se agregó `stream-assets/obs-overlays/*.zip` a `.gitignore` para no versionarlo.

### 10.2 Perfil Center Stage

- `perfil: "center-stage"` en `config/evento.js` activa `config/perfiles/center-stage.js`, que se mezcla sobre `evento.js`: tema, logos, 11 auspiciantes y textos («Empieza pronto», «Ya volvemos», «Auspician»). Fecha, lugar, redes, sitio y comentaristas siguen saliendo de `evento.js`.
- Logo horizontal (`logoEventoHorizontal`) en los encabezados y en la marca del gameplay; logo vertical en «Empieza pronto», patrocinadores y bracket.
- **Auspiciantes:** sin principal (los 11 con el mismo peso). Las tiras rotan tandas de 5 o 6 cada 8 s; el gameplay rota de a uno; la pantalla de patrocinadores los muestra a todos.
- **Santa Bárbara** es azul oscuro y no se lee sobre fondo oscuro: se muestra en blanco (`estilo: "blanco"`), igual que en el video del evento. Es la única alteración de color de un logo de terceros y se puede desactivar.
- Los nombres de los auspiciantes del perfil se leyeron de los propios logos.

### 10.3 Bracket Top 8 (`bracket.html` + `config/bracket.js`)

- Doble eliminación de 8: Winners Semifinal ×2, Winners Final, Losers Round 1 ×2, Losers Quarterfinal ×2, Losers Semifinal, Losers Final, Grand Final y reset opcional.
- Las líneas entre sets se calculan a partir de la posición de cada set (SVG). La línea del ganador se enciende cuando el set termina.
- Ganador resaltado y perdedor atenuado según el formato (BO3/BO5/BO7). Set «en juego» marcado. «Por definir» atenuado.
- No avanza ganadores solo (sin lógica de bracket ni start.gg, como pide la consigna).
- Mejora sobre el bracket del pack: aquel tenía los 10 sets en columnas sin conexiones y mezclaba winners con losers; acá winners va arriba, losers abajo y la Grand Final a la derecha, con el recorrido dibujado.

### 10.4 Correcciones encontradas en esta revisión

- La luz animada de «Empezamos pronto» se pintaba **encima** del logo (los elementos con transformaciones se pintan sobre los que no tienen posición); en Smash Hub se notaba poco, en Center Stage lavaba el logo. El logo ahora tiene su propia capa.
- La línea de Winners Final caía en vertical en lugar de ir a la Grand Final.
- La pantalla de patrocinadores tenía un tope de 4 secundarios.
- Los nombres de los auspiciantes 7 a 11 estaban asignados a archivos equivocados; se corrigió comparando cada archivo con su imagen.

### 10.5 Capturas nuevas

`08-bracket.png` (Top 8 a mitad de torneo, con datos de ejemplo de `previews/datos/bracket-ejemplo.js`), `08-bracket-vacio.png` y las siete escenas de Center Stage: `07-center-stage-{gameplay,versus,starting-soon,intermission,commentators,sponsors,bracket}.png`. Todas sin errores y sin pedidos a recursos externos.

### 10.6 Pendientes

- Redes, sitio y comentaristas reales de Center Stage (siguen los de ejemplo en `evento.js`).
- Confirmar con la organización si hay un auspiciante principal y si está bien mostrar Santa Bárbara en blanco.
- Probar en OBS 31+ con captura real, como en la sección 8.

## 11. Pack Center Stage v3: escenas con cámaras, cierre y Tournament Stream Helper

Pedido del 13/11/2026: actualizar todo con `CENTER-STAGE-OBS-PACK-v3.zip` (más escenas y conexión con TSH).

### 11.1 Qué traía la v3 y qué se hizo

| v3 | En el paquete |
| --- | --- |
| `gameplay-broadcast.html` (juego + 2 cámaras de jugadores) | Escena nueva con nuestro diseño: marcador igual al del gameplay, columna con cámaras, nombres y puntos por jugador, auspiciante rotando y pie con lema. **Mismas posiciones de cámara** que la v3 |
| `commentators-wide.html` (una cámara para toda la mesa) | Escena nueva: hueco 1280 × 720 en la misma posición, título «Mesa de análisis», dos placas de comentaristas y banda grande de auspiciantes |
| `ending.html` (cierre) | Escena nueva: «Nos vemos en stage» (CS) o «Gracias por ver» (Smash Hub), lema, redes, emblema con anillos y auspiciantes |
| `tsh-adapter.js` (lectura de TSH) | Lectura propia de TSH en `assets/js/overlay.js`, para **todas** las escenas y las dos identidades (ver 11.2). Se usó el adaptador del pack como referencia del esquema y se contrastó con los layouts oficiales de TSH |
| Santa Bárbara sobre placa blanca | Adoptado (`estilo: "placa"`): conserva los colores del logo, en lugar de pasarlo a blanco |
| Panel, servidor, videos | No se usan (sin panel ni servidor, como pide la consigna) |

Las posiciones de cámara de `commentators.html` (dos cámaras de 860 × 484) no se cambiaron: difieren de las del pack (810 × 453), porque la escena se diseñó antes.

### 11.2 Tournament Stream Helper

- Se activa con `?tsh=1` en la URL. El paquete se copia en `TSH/layout/<carpeta>/` y se usa por el servidor web de TSH. Lee `../../out/program_state.json` cada segundo, por XHR, de modo que funciona por http y también como archivo local en OBS.
- **Esquema usado**, contrastado el 13/11/2026 con `TournamentStreamHelper-layouts` (`scoreboard/index.js` e `include/globals.js`):
  - marcador: `score[N].team["1"|"2"]`, con `player[*].name`, `player[*].team` (prefijo), `team.score`, `teamName`;
  - partido: `phase`, `match`, `best_of` / `best_of_text`;
  - comentaristas: `commentary[*].name` y `twitter`.
- **Supuestos, según el adaptador del pack y no según los layouts oficiales:**
  - el bracket en `bracket.bracket.rounds` y `bracket.players.slot`;
  - el personaje en `player.character["1"].en_name|name`.
- **Personajes:** los nombres de TSH se convierten a los íconos del paquete, con alias para Hero, Piranha Plant, Incineroar, Pyra/Mythra, Min Min, Mii, etc. Si un personaje no tiene ícono, se oculta.
- **Top 8:** solo con la cola estándar de doble eliminación (winners 2-1-1-1 con reset, losers 2-2-1-1); si no coincide, no adivina y se queda con `config/bracket.js`. El reset aparece si la Grand Final la ganó el lado de losers y el reset tiene jugadores. El set que coincide con el marcador actual se marca «En juego».
- **Errores:** si no se puede leer el archivo, se conserva el último dato; el estado queda en `window.SH_TSH` (`ok`, `error`, `bracket`, `leido`).

**Prueba:** con un `program_state.json` simulado (`previews/datos/tsh-estado-ejemplo.json`), servido por HTTP local, en gameplay, versus, commentators-wide, gameplay-broadcast y bracket:
- nombres, prefijo, marcador, ronda «Losers Semi-Final», BO5;
- personajes «Pyra & Mythra» → `homura` y «Mr. Game & Watch» → `mr_game_and_watch`;
- comentaristas con `@`;
- los 11 sets del Top 8 en su lugar, con LSF «en juego».

Con una ruta inexistente, `SH_TSH.ok = false`, con el error HTTP 404, y la escena sigue con los datos manuales. **No se probó contra una instalación real de TSH** ni con un torneo real.

### 11.3 Capturas nuevas

`09-gameplay-broadcast(-simulado).png`, `10-commentators-wide(-simulado).png`, `11-ending.png`, `07-center-stage-{gameplay-broadcast,commentators-wide,ending}.png` y, desde TSH simulado, `12-tsh-bracket-center-stage.png` y `12-tsh-gameplay-broadcast.png`. Total: 31 capturas, sin errores ni pedidos externos. Las vistas `*-simulado` usan `previews/broadcast-simulado.html`.

Corrección encontrada en la revisión: los marcos de las cámaras chicas heredaban la posición vertical de su contenedor y salían desplazados.

### 11.4 Pendientes

- Probar con TSH real: confirmar el campo de personajes y el bracket con un torneo de start.gg cargado en TSH.
- Decidir si `commentators.html` debe usar las medidas de la v3 (810 × 453).

## 12. TSH no mostraba los datos: diagnóstico y corrección

Reporte del 13/11/2026: con TSH conectado, el overlay seguía mostrando placeholders.

### 12.1 Causas posibles, confirmadas en el código de TSH

Se revisaron `TSHWebServer.py`, `TSHWebServerActions.py` y `StateManager.py` de `joaorb64/TournamentStreamHelper`:
- El servidor web de TSH usa por defecto el **puerto 5500**, no el 5000 que figuraba de ejemplo (tomado del pack v3).
- El servidor sirve la carpeta de trabajo de TSH entera (`/layout/…`, `/out/…`) y tiene la ruta **`/program-state`**, que devuelve `{ state, delta_index }`.
- `StateManager` escribe `./out/program_state.json` en cada cambio.

Con eso, el modo anterior fallaba sin avisar en tres situaciones:
1. **OBS con «Archivo local»:** no se puede agregar `?tsh=1`, así que la escena quedaba en modo manual con los placeholders. Es la causa más probable.
2. **Una carpeta de más al descomprimir el ZIP** (`layout/CENTER-STAGE-OVERLAYS/center-stage-overlays/`): `../../out/program_state.json` no existía.
3. **URL con un puerto equivocado.**

Además, los campos que TSH dejaba vacíos mantenían los ejemplos de `config/` («Winners Final», «Comentarista 1»).

### 12.2 Cambios en `assets/js/overlay.js`

- `tsh: true` en `config/evento.js` activa TSH sin parámetros de URL, así que funciona con «Archivo local». También se agregan `scoreboard` y `diagnostico`.
- **Búsqueda automática:** primero `/program-state` (desenvuelve `state`); después `../../out/program_state.json`, `../out/…`, `../../../out/…` y `/out/program_state.json`. Recuerda la que funcionó.
- **Compatibilidad** con el formato de un solo marcador (`score.team`) de versiones viejas de TSH.
- **Aviso rojo en pantalla** cuando TSH está activado y no hay datos (después de 4 s), con el motivo. Se apaga con `diagnostico: false`.
- **En modo TSH**, ronda, formato y comentaristas toman siempre el valor de TSH, aunque esté vacío. Las placas de comentaristas sin nombre se ocultan.
- Lectura cada segundo con TSH; cada 2 s sin TSH.
- La herramienta de capturas reintenta si Windows tiene un PNG bloqueado.

### 12.3 Pruebas

Con una carpeta TSH simulada (`TSH/out/program_state.json` y el paquete en `TSH/layout/CENTER-STAGE-OVERLAYS/center-stage-overlays/`) y un servidor que imita al de TSH en el puerto 5500:

| Caso | Resultado |
| --- | --- |
| A. URL con `?tsh=1`, carpeta de más | Lee de `/program-state`; nombres, marcador, ronda y BO5 correctos; Top 8 reconocido |
| B. URL sin `?tsh=1` y `tsh: false` | Modo manual con placeholders (reproduce el reporte) |
| C. URL sin `?tsh=1`, `tsh: true` | Lee de `/program-state` |
| D. Archivo local como en OBS, `tsh: true`, carpeta de más | Lee de `../../../out/program_state.json` |
| E. TSH activado y archivo inexistente | Aviso rojo con el error HTTP 404; datos manuales intactos |

Sin errores de JavaScript; las 31 capturas se regeneraron sin errores. Sigue pendiente una prueba con TSH real (sección 11.4).

## 13. Ajustes de Center Stage para el evento (14 y 15 de noviembre)

Pedido del 13/11/2026.

| Pedido | Cambio |
| --- | --- |
| Fechas 14 y 15 | `fecha: "14 y 15 de noviembre"` en el `evento.js` del ZIP. El perfil no fija la fecha: queda en `evento.js` para que se pueda editar en un solo lugar |
| Gameplay sin auspiciantes ni logo | Opción `gameplay: { marca: false, patrocinadores: false }` en el perfil. `gameplay.html` queda solo con el marcador; `gameplay-broadcast.html`, con marcador y cámaras (sin logo, auspiciante ni pie) |
| Banderas de start.gg | Con TSH: `player.country.asset`, la ruta dentro de la carpeta de TSH, mismo criterio que los layouts oficiales. Se muestra en el marcador, las placas de cámara, el versus y las filas del bracket. Se resuelve desde la raíz de TSH (`/program-state` → servidor; `…/out/program_state.json` → carpeta). Si no hay bandera o no carga, no se muestra |
| Auspiciantes en carrusel y arriba | Opciones `carrusel` y `auspiciantesArriba`. La barra pasa al borde superior y se desliza sin cortes; se reconstruye solo si cambia la lista, así que las actualizaciones de TSH no la reinician. Cada escena reacomoda su contenido para no chocar con la barra |
| Logo más grande y centrado | Opción `logoCentrado`. Logo horizontal centrado arriba en versus, comentaristas, intermedio y bracket (reemplaza al logo de la esquina; en el bracket, también al emblema lateral y a la fecha). En la mesa de análisis, logo vertical en la columna |
| Frases poco claras | Cierre: «Gracias por / acompañarnos» y «Hasta el próximo Center Stage», sin lema. Se quitó «El escenario es tuyo» (cierre, pie y cinta) y «En la cabina» pasa a «Comentaristas» |

El ZIP ahora lo arma `herramientas/empaquetar_center_stage.py`, que además rechaza el paquete si quedara algún placeholder en `evento.js`. Su LEEME está versionado en `herramientas/paquete-center-stage/LEEME.txt`.

**Pruebas:**
- Banderas con TSH simulado (países de ejemplo en `previews/datos/`): 4 en el gameplay con cámaras, 18 en el bracket y 2 en el versus.
- ZIP final descomprimido dentro de una carpeta TSH simulada y abierto como archivo local, como en OBS: las 10 escenas leen TSH y no hay errores ni pedidos externos.
- 32 capturas regeneradas; las de Smash Hub no cambian.

## 14. Logo de «Empieza pronto» y cámaras en el gameplay

Reporte del 13/11/2026, con capturas.

- **Logo descentrado en «Empieza pronto»:** el logo del evento se forzaba a un cuadrado de 460 × 460, pero el de Center Stage mide 1271 × 1175. Se deformaba y no quedaba centrado dentro de los anillos. Ahora usa `object-fit: contain` (440 px) y el emblema queda alineado con el bloque de título (centro y ≈ 560). En el cierre ya estaba bien.
- **Una cámara por jugador en `gameplay.html`:** opción `gameplay.camaras` (activada en el perfil de Center Stage). Son dos cámaras de 416 × 234 (16:9) abajo a la izquierda (x 32, y 790) y abajo a la derecha (x 1472, y 790), fuera de la franja del HUD de porcentajes y stocks (x 480–1440). Cada una tiene una placa con bandera, nombre y marcador del jugador. Las cámaras van debajo de la fuente. Con la opción activada, se ocultan la marca y el auspiciante de las esquinas. Sin la opción (Smash Hub), el gameplay no cambia.
- **Prueba:** ZIP regenerado y abierto dentro de una carpeta TSH simulada: las 10 escenas leen TSH, el gameplay muestra las dos cámaras con nombres y banderas de TSH y no hay errores.

## 15. Anillos centrados en su zona y redes de Center Stage

Reporte del 13/11/2026, con un dibujo de la ubicación esperada.

- **El problema real era de la grilla:** el emblema (luz, anillos y logo) se apila en una grilla de una celda. La luz es más grande que el contenedor (900 px en 700), así que la celda se agrandaba y todo el conjunto se corría unos 100 px a la derecha y hacia abajo. Pasaba en «Empieza pronto» y en el cierre, con los dos temas. Ahora la celda mide lo mismo que el contenedor (`grid-template: 100% / 100%`) y la luz desborda pareja hacia los dos lados.
- **Center Stage, «Empieza pronto»:** conjunto de 640 px centrado en (360, 490), en la franja izquierda debajo de la barra, como en el dibujo. Logo de 400 px y anillos de 540 y 620 px.
- **Center Stage, cierre:** mismo criterio, centrado en la franja derecha (x ≈ 1455).
- **Tildes:** los títulos grandes recortaban la tilde de la Ñ («ACOMPAÑARNOS»). Las líneas que se achican solas tienen ahora aire arriba.
- **Redes de Center Stage:** Instagram `@centerstagepy` y start.gg `start.gg/CSPY`, sin Discord ni sitio, en el perfil. El ZIP quita `redes` y `sitio` de su `evento.js` y deja un comentario que indica dónde están, porque el perfil los pisaría.

ZIP regenerado y probado dentro de la carpeta TSH simulada: las 10 escenas leen TSH, las redes aparecen en «Empieza pronto», auspiciantes y cierre, y no queda ningún texto de ejemplo.
