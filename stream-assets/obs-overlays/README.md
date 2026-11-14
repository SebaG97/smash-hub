# Overlays de Smash Hub para OBS

Diez escenas para transmitir torneos de Smash Ultimate, con dos identidades: Smash Hub (por defecto) y Center Stage. Son archivos locales (HTML, CSS e imágenes): no necesitan internet, ni instalar nada, ni un servidor. Opcionalmente leen los datos de **Tournament Stream Helper** (ver más abajo).

| Escena | Archivo | Fondo |
| --- | --- | --- |
| Gameplay (marcador) | `gameplay.html` | **Transparente**: va encima de la captura del juego |
| Versus / próximo set | `versus.html` | Opaco |
| Empezamos pronto | `starting-soon.html` | Opaco |
| Volvemos enseguida | `intermission.html` | Opaco |
| Comentaristas | `commentators.html` | Opaco, con **dos huecos transparentes** para cámaras |
| Patrocinadores | `sponsors.html` | Opaco |
| Bracket Top 8 | `bracket.html` | Opaco |
| Gameplay con cámaras de jugadores | `gameplay-broadcast.html` | Opaco, con **huecos** para juego y dos cámaras |
| Mesa de análisis (una cámara) | `commentators-wide.html` | Opaco, con **un hueco** para la cámara general |
| Cierre | `ending.html` | Opaco |

Las capturas de cada una están en [`previews/`](previews/).

## Cargar en OBS

1. **Fuentes → + → Navegador** (Browser Source).
2. Marcá **Archivo local** y elegí el `.html` de la escena.
3. **Ancho 1920, Alto 1080.** No cambies el tamaño: si la escena es más chica, escalá la fuente en el lienzo.
4. Dejá vacío el campo **CSS personalizado** (OBS trae una regla por defecto; borrala si aparece).
5. Recomendado: marcá **Actualizar el navegador cuando la escena se active**, así las animaciones de entrada se ven cada vez que cambiás de escena.

### Gameplay

Poné `gameplay.html` **encima** de la captura de la consola. El marcador ocupa el centro de arriba; el logo, la esquina inferior izquierda; los patrocinadores, la inferior derecha. No se tapan los porcentajes, los stocks ni el temporizador (ver `previews/01-gameplay-zonas-hud.png`).

### Comentaristas

Poné las dos cámaras **debajo** de `commentators.html`, con estas posiciones y tamaños (16:9):

| Cámara | x | y | Ancho × alto |
| --- | --- | --- | --- |
| 1 | 70 | 250 | 860 × 484 |
| 2 | 990 | 250 | 860 × 484 |

En OBS: clic derecho en la cámara → **Transformar → Editar transformación** y cargá esos valores. Si la cámara no es 16:9, usá **Recortar** o «Ajustar a la caja delimitadora».

### Gameplay con cámaras y mesa de análisis

Mismas posiciones que el pack oficial de Center Stage (v3), así que una escena de OBS ya armada para ese pack sirve igual. Todas las fuentes van **debajo** del HTML y recortadas a 16:9:

| Escena | Fuente | x | y | Ancho × alto |
| --- | --- | --- | --- | --- |
| `gameplay-broadcast.html` | Captura del juego | 24 | 140 | 1536 × 864 |
| | Cámara jugador 1 | 1584 | 225 | 320 × 180 |
| | Cámara jugador 2 | 1584 | 520 | 320 × 180 |
| `commentators-wide.html` | Cámara general | 80 | 140 | 1280 × 720 |

La cámara 1 corresponde al jugador de la izquierda del marcador. Si cambiás los lados, revisá qué cámara física es de cada jugador.

## Con Tournament Stream Helper (TSH)

Las escenas pueden tomar los datos de competencia directamente de TSH, que ya se conecta con start.gg. No hace falta otro token y el paquete **solo lee**: no escribe en TSH ni en start.gg.

1. Copiá la carpeta `obs-overlays` completa dentro de la carpeta `layout` de tu TSH (por ejemplo, `TSH/layout/smash-hub/`). Si al descomprimir quedó una carpeta de más (`TSH/layout/ZIP/obs-overlays/`), también funciona.
2. Activá TSH en `config/evento.js`:
   ```js
   tsh: true,
   ```
3. En OBS, cualquiera de las dos formas:
   - **Archivo local** (lo más simple): elegí el `.html` dentro de `TSH/layout/…`.
   - **URL del servidor web de TSH** (puerto **5500** por defecto): `http://127.0.0.1:5500/layout/smash-hub/gameplay.html`. Con esta forma también se puede activar TSH agregando `?tsh=1` a la URL, sin tocar `evento.js`.
4. Cargá el set en TSH como siempre: las escenas se actualizan cada segundo.

**Dónde busca los datos, en orden:** la ruta `/program-state` del servidor web de TSH; `out/program_state.json`, dos carpetas más arriba (la ubicación estándar `TSH/layout/<carpeta>/`); y ese mismo archivo una carpeta más arriba o más abajo. Si tu instalación es distinta: `?tshRuta=ruta/al/program_state.json`.

**Qué toma de TSH:** nombres (o nombre de equipo en dobles), prefijo, personaje, marcador, ronda, formato (BO3/BO5), los dos primeros comentaristas y el **Top 8 completo**, si el final del bracket es el estándar de doble eliminación (winners 2-1-1 más reset, losers 2-2-1-1). El set del Top 8 que coincide con el marcador se marca solo como «En juego». Si el bracket no tiene esa forma, se usa `config/bracket.js`. Lo que TSH deja vacío queda vacío: no aparecen los ejemplos de `config/`.

**Qué sigue saliendo de `config/`:** evento, fecha, lugar, logos, patrocinadores, redes, textos y perfil.

**Si no aparecen los datos:** con TSH activado y sin datos, la escena muestra un **aviso rojo** con el motivo (por ejemplo, TSH cerrado o el paquete fuera de `TSH/layout/`). Desaparece en cuanto encuentra los datos. Se apaga con `diagnostico: false`. Si TSH se cae durante el stream, se conserva el último dato recibido. Para más detalle, abrí la escena en Chrome y escribí `SH_TSH` en la consola: `ok: true` significa que está leyendo, `fuente` dice de dónde lee y `bracket: true` indica que el Top 8 se reconoció.

Para otro marcador de TSH: `scoreboard: "2"` en `evento.js`, o `&scoreboardNumber=2` en la URL.

## Cambiar textos, marcadores y patrocinadores

Todo se edita en los archivos de la carpeta `config/`, con cualquier editor de texto (Bloc de notas sirve). Cambiá solo lo que está entre comillas y guardá: **las escenas abiertas en OBS se actualizan solas en 2 segundos**, sin refrescar.

### `config/partida.js` — durante el torneo

```js
ronda: "Winners Final",
formato: "BO5",
jugador1: { nombre: "Jugador 1", equipo: "", personaje: "", marcador: 0 },
jugador2: { nombre: "Jugador 2", equipo: "", personaje: "", marcador: 0 },
```

- **marcador**: partidas ganadas en el set. Al llegar a 2 (BO3) o 3 (BO5), el número se pone dorado.
- **equipo**: prefijo (por ejemplo `"SCP"`). Vacío = sin prefijo.
- **personaje**: nombre de archivo de `assets/images/personajes/` sin `.svg` (`"mario"`, `"pikachu"`, `"cloud"`, `"pokemon_trainer"`…). Solo se usa en el versus. Vacío = muestra la inicial del jugador.
- **siguiente**: el set que anuncia «Volvemos enseguida».
- **mostrar**: `marca: false` o `patrocinadores: false` apaga esas esquinas del gameplay.

Los nombres largos se achican solos para entrar.

### `config/evento.js` — una vez por evento

Nombre del torneo, fecha, hora, lugar, sitio web, redes (hasta 3), comentaristas, patrocinadores, textos de las pantallas y mensajes de la cinta. Lo marcado con `REEMPLAZAR` es un ejemplo.

- **inicio**: si ponés una fecha (`"2026-11-14T15:00:00-03:00"`), «Empezamos pronto» muestra una cuenta regresiva. Vacío = no aparece.
- **Patrocinadores**: copiá los logos a `assets/images/patrocinadores/` (PNG o SVG **con fondo transparente**, idealmente claros o blancos) y escribí la ruta en `logo`. Si un patrocinador no tiene logo, borrá la línea `logo` y se muestra su nombre en texto. Los que vienen son **placeholders** marcados como tales.
- El gameplay rota todos los patrocinadores (principal y secundarios) cada 8 segundos.

### `config/bracket.js` — durante el Top 8

Un bloque por set (`WSF1`, `WSF2`, `WF`, `LR1A`, `LR1B`, `LQFA`, `LQFB`, `LSF`, `LF`, `GF`, `RESET`) con `j1`, `p1`, `j2`, `p2` (jugadores y sets ganados).

- Nombre vacío = «Por definir». Cuando alguien llega a las victorias del formato (3 en BO5), el set queda terminado: el ganador se resalta y su línea hacia el siguiente set se enciende.
- **No avanza solo**: escribí el ganador en el set siguiente.
- `enJuego: "LSF"` marca el set que se está jugando.
- El reset de Grand Final aparece si tiene datos o con `reset: true`.

### Cambios rápidos desde la URL (opcional)

Para una escena puntual, los datos también se pueden pasar en la URL de la fuente (desmarcá «Archivo local» y usá la ruta `file:///…`). Tienen prioridad sobre `config/`:

```
file:///C:/ruta/obs-overlays/gameplay.html?p1=Nombre&p2=Nombre&s1=1&s2=0&ronda=Grand%20Final
```

Parámetros: `p1`, `p2`, `s1`, `s2`, `e1`, `e2` (equipos), `c1`, `c2` (personajes), `ronda`, `formato`, `evento`, `tema`, `perfil`, `logoEvento`, `inicio`, `bracket` (otro archivo de bracket), `tsh=1`, `scoreboardNumber`, `tshRuta` (ubicación exacta del estado de TSH).

## Center Stage

En `config/evento.js`, cambiá una sola línea:

```js
perfil: "center-stage",
```

Eso activa todo lo de `config/perfiles/center-stage.js`: paleta oficial (fucsia `#E32C64`, violeta `#30244A`, negro `#08070C`, blanco `#F8F5FB`), logos oficiales vertical y horizontal, los 11 auspiciantes y los textos del evento («Empieza pronto», «Ya volvemos», «Auspician»). Lo que el perfil no define (fecha, hora, lugar, redes, sitio, comentaristas) se sigue tomando de `evento.js`. Para volver a Smash Hub: `perfil: ""`.

- Los logos vienen del pack oficial `CENTER-STAGE-OBS-PACK`; se les quitó solo el fondo negro (los JPEG originales están en `assets/images/eventos/center-stage/originales/`).
- Con 11 auspiciantes, las tiras muestran tandas de 5 o 6 que cambian cada 8 segundos; la pantalla de patrocinadores los muestra a todos.
- Santa Bárbara (azul oscuro) va sobre una placa clara con sus colores originales, como en el pack v3 (`estilo: "placa"`). Alternativa: `estilo: "blanco"`.
- Para destacar un auspiciante como principal, completá `principal` en el perfil.

El perfil también activa opciones de composición pensadas para la pantalla gigante del evento (se pueden usar con cualquier perfil):

| Opción | Efecto |
| --- | --- |
| `auspiciantesArriba: true` | La barra de auspiciantes va arriba: la franja inferior no se ve en la pantalla gigante |
| `carrusel: true` | Los auspiciantes se deslizan en lugar de cambiar por tandas |
| `logoCentrado: true` | El logo del evento va grande y centrado, en lugar de chico en una esquina |
| `gameplay: { marca: false, patrocinadores: false }` | `gameplay.html` y `gameplay-broadcast.html` quedan solo con marcador y cámaras |

**Banderas:** con TSH, el marcador, las placas de cámara, el versus y el bracket muestran la bandera del país de cada jugador, tomada de start.gg. Usan las imágenes que trae TSH; sin TSH, no se muestran.

**ZIP para el stream:** `python herramientas/empaquetar_center_stage.py` arma `stream-assets/dist/CENTER-STAGE-OVERLAYS.zip`, con Center Stage y TSH activados, la fecha del evento, sin textos de ejemplo y con su `LEEME.txt` (`herramientas/paquete-center-stage/`).

Para otro evento con identidad propia: copiá `config/perfiles/center-stage.js` y `assets/css/temas/center-stage.css` con otro nombre.

## Estructura

```
obs-overlays/
├── gameplay.html, versus.html, starting-soon.html,
│   intermission.html, commentators.html, sponsors.html, bracket.html,
│   gameplay-broadcast.html, commentators-wide.html, ending.html
├── config/
│   ├── evento.js          datos del evento (se edita una vez)
│   ├── partida.js         set actual (se edita entre partidas)
│   ├── bracket.js         Top 8 (se edita durante el Top 8)
│   └── perfiles/center-stage.js   identidad completa de Center Stage
├── assets/
│   ├── css/               base.css (identidad compartida) + una hoja por escena
│   │   └── temas/         center-stage.css
│   ├── js/overlay.js      carga config/ y completa las escenas (no hace falta tocarlo)
│   ├── fonts/             Big Shoulders Display y Atkinson Hyperlegible (licencia OFL)
│   └── images/
│       ├── marca/         logo de Smash Club Paraguay (original y recorte circular)
│       ├── personajes/    íconos de personajes (los mismos del sitio)
│       ├── patrocinadores/ placeholders
│       ├── patrocinadores/center-stage/ los 11 auspiciantes
│       └── eventos/center-stage/ logos oficiales (y originales/)
├── previews/              capturas PNG y dos vistas previas con gameplay y cámaras simuladas
└── herramientas/capturar.py  regenera las capturas (solo para mantenimiento)
```

## Requisitos y límites

- OBS Studio 31 o posterior: su fuente de navegador usa Chromium 127, que soporta todo lo que usan las escenas (`color-mix()`, máscaras, `translate`). En versiones anteriores algunos fondos y colores pueden no verse. También se ven bien en Chrome o Edge actuales.
- Todo es local y con rutas relativas: se puede mover la carpeta completa a otra PC.
- Las fuentes vienen incluidas, con su licencia SIL Open Font License en `assets/fonts/`.
- Las posiciones del HUD de Smash Ultimate usadas para dejar zonas libres son aproximadas (1 vs 1, 1920 × 1080). Conviene comprobarlas una vez con una captura real.
- `previews/*-simulado.html` son solo vistas previas: **no** cargarlas en OBS.

## Regenerar las capturas

Solo para quien mantiene el paquete. Necesita Python 3, `pip install playwright` y Chrome o Edge:

```
python herramientas/capturar.py
```
