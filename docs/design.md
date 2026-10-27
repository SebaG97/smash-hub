# Diseño visual

Notas de la pasada de rediseño hecha con la skill `frontend-design` (27/10/2026). Sirven para mantener la coherencia en los cambios futuros.

## Brief

Hub de la escena de Smash Ultimate en Paraguay (Smash Club Paraguay). Lo usan sobre todo jugadores, muchas veces desde el celular, para ver dónde está cada uno en el ranking, quién juega qué personaje y qué torneos hubo; también los organizadores. El cliente pidió usar los colores del logo y que el sitio no se viera "hecho con IA": nada de grillas de tarjetas ni degradés.

## Tokens

| Nombre | Hex | Uso |
| --- | --- | --- |
| Concreto | `#26221f` | Fondo (el gris cálido del logo, no un casi-negro) |
| Losa | `#302b27` | Superficies de herramientas y filas abiertas, con moderación |
| Hueso | `#efe9df` | Texto |
| Ceniza | `#a2988d` | Texto secundario, reglas de tabla |
| Fuego | `#e5541b` | Acciones, puestos 2 y 3, subrayados |
| Oro | `#f3a81f` | Solo el 1.º puesto y el foco de teclado |

Tipografía: *Big Shoulders Display* (700–900) para títulos, nombres en tablas y cifras; *Atkinson Hyperlegible* para el texto. Escala aproximada 1,25.

## Principios

- **Un solo elemento audaz:** los números de puesto, grandes e inclinados como en la pantalla de resultados del juego, junto a los íconos de stock de los mains. El resto, sobrio.
- **Listas y tablas, no tarjetas.** Filas separadas por reglas; las superficies `Losa` son solo para herramientas de organizadores.
- **Sin** degradés, brillos, sombras de color, etiquetas en mayúsculas sobre los títulos, flechas "↗" en los enlaces ni "01/02/03" decorativos. Los números solo aparecen donde son una secuencia real: puestos y seeds.
- La portada abre con lo más propio de la escena: el top 8 del ranking publicado y los últimos torneos.
- El texto en tono de usuario y en oraciones simples; los metadatos van como oraciones, no unidos con puntos medios.

## Íconos de personajes

`apps/web/public/characters/*.svg` son los íconos de stock de los 84 personajes de Smash Ultimate, en vectores a color de 200×200. Los aportó el responsable del proyecto el 27/10/2026, a partir de una colección de la comunidad sin licencia incluida. Son arte de Nintendo y se usan con fines comunitarios. Antes de copiarlos se limpiaron: sin declaración XML ni DOCTYPE, sin `id`, cifras a un decimal y `viewBox` agregado donde faltaba; se verificó que no tengan scripts ni enlaces externos. `src/lib/characters.ts` relaciona los nombres de start.gg con los archivos; algunos usan el nombre interno del juego (`gaogaen` = Incineroar, `homura` = Pyra & Mythra, `packun_flower` = Piranha Plant), y los tres Mii comparten `mii_fighter`. Si no hay ícono local (por ejemplo "Random Character"), se usa la imagen de start.gg.

## Pasada de color (Misión 11)

El color sale del propio juego: cada jugador toma el color característico de su main (`src/lib/character-colors.ts`, generado desde los SVG, con 16 elegidos a mano). Se usa en la franja de las filas del ranking y la portada, en el fondo teñido del 1.º y en la cabecera de la ficha. El W-L lleva una barra verde y roja; el menú marca la sección actual; la portada tiene un buscador de jugadores, y las páginas de ranking y seeding tienen enlace para volver.

## Ficha del jugador y fondo (Misión 12)

- **Fondo:** grano de concreto muy sutil en todo el sitio (la textura del logo, generada con `feTurbulence`). En la ficha, la parte superior toma el tono del main del jugador y se funde con el concreto.
- **Ficha:** cabecera con el ícono grande del main; franja con puesto en el ranking (número inclinado en oro), récord con barra, % de victorias, torneos y último torneo; pestañas **Resumen** (mains como "stocks" con el color de cada personaje, y los tres mejores resultados según el tamaño del bracket), **Estadísticas**, **Rivales** (con el ícono del main de cada rival y la barra del H2H) e **Historial**.

## Récords, emblemas e imágenes (Misión 13)

- **Emblemas:** fila de chapas con el nombre en la tipografía de títulos y el motivo debajo. Oro para los de títulos y el liderato, fuego para las hazañas (sorpresas, remontadas, rachas) y hueso para el resto.
- **Sorpresas:** el factor va como `+N` en fuego, a la izquierda, como un marcador.
- **Jugador del mes:** la única pieza destacada de la portada, con el ícono grande del main y su color de fondo.
- **Imágenes para redes:** cuadradas (1080×1080) para Instagram y WhatsApp, con la misma receta: concreto, logo, números de puesto inclinados (oro el 1.º, fuego 2.º y 3.º) y la franja de color del main de cada jugador.

## Imagen de podio (Misión 14)

La imagen para redes pasa a ser un podio: el 1.º ocupa la mitad izquierda con el render oficial de su main sobre el color del personaje; el 2.º y el 3.º van a la derecha, medianos; del 4.º al 8.º, tarjetas con medio cuerpo; del 9.º al 12.º, una fila chica con el ícono de stock. Los nombres van sobre una banda de concreto al pie de cada tarjeta, con el número de puesto inclinado. Los organizadores eligen el traje de cada jugador desde su ficha (sección «Traje en las imágenes», visible solo con la clave). Renders: smashbros.com, ver ADR-015. Con «Personalizar imagen» el organizador puede reemplazar el render de cualquier puesto por una foto propia (llena la tarjeta) o un PNG recortado (va como el render).
