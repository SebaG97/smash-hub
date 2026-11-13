# SH-OBS-01 — Overlays profesionales para OBS

Fecha: 13/11/2026. Paquete: [stream-assets/obs-overlays/](../../stream-assets/obs-overlays/README.md). Primera versión para revisión estética; no se hizo push ni despliegue.

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
