# Overlays de Smash Hub para OBS

Seis escenas para transmitir torneos de Smash Ultimate. Son archivos locales (HTML, CSS e imágenes): no necesitan internet, ni instalar nada, ni un servidor.

| Escena | Archivo | Fondo |
| --- | --- | --- |
| Gameplay (marcador) | `gameplay.html` | **Transparente**: va encima de la captura del juego |
| Versus / próximo set | `versus.html` | Opaco |
| Empezamos pronto | `starting-soon.html` | Opaco |
| Volvemos enseguida | `intermission.html` | Opaco |
| Comentaristas | `commentators.html` | Opaco, con **dos huecos transparentes** para cámaras |
| Patrocinadores | `sponsors.html` | Opaco |

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

## Cambiar textos, marcadores y patrocinadores

Todo se edita en dos archivos de la carpeta `config/`, con cualquier editor de texto (Bloc de notas sirve). Cambiá solo lo que está entre comillas y guardá: **las escenas abiertas en OBS se actualizan solas en 2 segundos**, sin refrescar.

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

### Cambios rápidos desde la URL (opcional)

Para una escena puntual, los datos también se pueden pasar en la URL de la fuente (desmarcá «Archivo local» y usá la ruta `file:///…`). Tienen prioridad sobre `config/`:

```
file:///C:/ruta/obs-overlays/gameplay.html?p1=Nombre&p2=Nombre&s1=1&s2=0&ronda=Grand%20Final
```

Parámetros: `p1`, `p2`, `s1`, `s2`, `e1`, `e2` (equipos), `c1`, `c2` (personajes), `ronda`, `formato`, `evento`, `tema`, `logoEvento`, `inicio`.

## Variante Center Stage

1. Copiá el logo oficial a `assets/images/eventos/center-stage/logo.png` (fondo transparente).
2. En `config/evento.js`:
   ```js
   tema: "center-stage",
   evento: "Center Stage",
   logoEvento: "assets/images/eventos/center-stage/logo.png",
   ```
3. Cuando estén los colores oficiales, reemplazá los valores de `assets/css/temas/center-stage.css`. **Los que trae son provisionales** (un turquesa para probar que la variante funciona), no la identidad del torneo.

Con `logoEvento`, el logo del torneo reemplaza al del club en el gameplay, «Empezamos pronto», «Volvemos enseguida», comentaristas y patrocinadores; el versus muestra los dos.

## Estructura

```
obs-overlays/
├── gameplay.html, versus.html, starting-soon.html,
│   intermission.html, commentators.html, sponsors.html
├── config/
│   ├── evento.js          datos del evento (se edita una vez)
│   └── partida.js         set actual (se edita entre partidas)
├── assets/
│   ├── css/               base.css (identidad compartida) + una hoja por escena
│   │   └── temas/         center-stage.css
│   ├── js/overlay.js      carga config/ y completa las escenas (no hace falta tocarlo)
│   ├── fonts/             Big Shoulders Display y Atkinson Hyperlegible (licencia OFL)
│   └── images/
│       ├── marca/         logo de Smash Club Paraguay (original y recorte circular)
│       ├── personajes/    íconos de personajes (los mismos del sitio)
│       ├── patrocinadores/ placeholders
│       └── eventos/center-stage/ placeholder del logo
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
